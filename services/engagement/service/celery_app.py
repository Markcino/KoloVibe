"""RabbitMQ-backed Celery worker bootstrap for the engagement service.

Not imported by Django's HTTP settings. Workers require an explicitly provisioned
RabbitMQ account and verified TLS. No production deployment is configured here.
"""
import os
import ssl
from urllib.parse import urlsplit

SERVICE = "engagement"
QUEUE = "kolovibe.engagement"


def validate_broker_url(value: str) -> str:
    """Require an authenticated, TLS-only RabbitMQ URI without exposing secrets."""
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "amqps"
            and bool(parsed.hostname)
            and bool(parsed.username)
            and bool(parsed.password)
            and parsed.port in (None, 5671)
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise RuntimeError(
            "KOLOVIBE_RABBITMQ_URL must be an authenticated amqps:// URI "
            "using port 5671 with no query or fragment"
        )
    return value


def build_app():
    """Initialize the worker for local development or an approved staging capability.

    Staging reads the broker URI from an owner-only secret file and verifies the broker against an explicit CA;
    it runs only when the `points` capability is approved for this service.
    """
    environment = os.getenv("KOLOVIBE_ENV")
    ca_file = None
    if environment == "local":
        broker = validate_broker_url(os.getenv("KOLOVIBE_RABBITMQ_URL", ""))
    elif environment == "staging" and "points" in os.getenv("KOLOVIBE_STAGING_CAPABILITIES", "").split(","):
        from staging_runtime import broker_ca, broker_url

        broker, ca_file = validate_broker_url(broker_url()), broker_ca()
    else:
        raise RuntimeError("Celery worker deployment is blocked until environment review")

    # Imported only by the worker entrypoint. Celery must be added to the
    # existing hashed dependency lock before the worker can be shipped.
    from celery import Celery

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "service.settings")
    app = Celery("kolovibe-engagement")
    app.conf.update(
        broker_url=broker,
        broker_use_ssl={"cert_reqs": ssl.CERT_REQUIRED, **({"ca_certs": ca_file} if ca_file else {})},
        broker_connection_retry_on_startup=True,
        broker_transport_options={"confirm_publish": True},
        broker_heartbeat=30,
        task_default_queue=QUEUE,
        task_serializer="json",
        accept_content=["json"],
        result_backend=None,
        task_ignore_result=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_publish_retry=True,
        task_publish_retry_policy={
            "max_retries": 3,
            "interval_start": 0,
            "interval_step": 1,
            "interval_max": 3,
        },
    )
    return app


# Explicit worker entrypoint: celery -A service.celery_app:app worker -Q kolovibe.engagement
# HTTP service startup does not import this module.
app = build_app()

@app.task(name="kolovibe.engagement.event", ignore_result=True)
def receive_event(event_id, event_type, payload):
    """Persist an idempotent receive marker, not unapproved engagement/point awards."""
    if not isinstance(payload, dict) or not isinstance(event_type, str):
        raise ValueError("Invalid event payload")
    import django
    django.setup()
    from django.db import transaction
    from .events import accept_once
    with transaction.atomic():
        return accept_once(event_id, event_type)
