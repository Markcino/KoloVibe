"""RabbitMQ-backed Celery worker for Identity: erasure confirmations (Decision C slice 2a).

Not imported by Django's HTTP settings. The worker needs an explicitly provisioned RabbitMQ account and verified TLS,
like Engagement and Points. Staging runs it only with the `account_management` capability and an approved broker plan.
"""
import os
import ssl
from urllib.parse import urlsplit

from django.db import DatabaseError

QUEUE = "kolovibe.identity"


def validate_broker_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "amqps" and bool(parsed.hostname) and bool(parsed.username)
                 and bool(parsed.password) and parsed.port in (None, 5671) and not parsed.query and not parsed.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise RuntimeError("KOLOVIBE_RABBITMQ_URL must be an authenticated amqps:// URI using port 5671 with no query or "
                           "fragment")
    return value


def build_app():
    environment = os.getenv("KOLOVIBE_ENV")
    ca_file = None
    if environment == "local":
        broker = validate_broker_url(os.getenv("KOLOVIBE_RABBITMQ_URL", ""))
    elif environment == "staging" and "account_management" in os.getenv("KOLOVIBE_STAGING_CAPABILITIES", "").split(","):
        from staging_runtime import broker_ca, broker_url

        broker, ca_file = validate_broker_url(broker_url()), broker_ca()
    else:
        raise RuntimeError("Celery worker deployment is blocked until environment review")
    from celery import Celery

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "service.settings")
    app = Celery("kolovibe-identity")
    app.conf.update(
        broker_url=broker,
        broker_use_ssl={"cert_reqs": ssl.CERT_REQUIRED, **({"ca_certs": ca_file} if ca_file else {})},
        broker_connection_retry_on_startup=True, broker_transport_options={"confirm_publish": True},
        broker_heartbeat=30, task_default_queue=QUEUE, task_serializer="json", accept_content=["json"],
        result_backend=None, task_ignore_result=True, task_acks_late=True, task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1, task_publish_retry=True,
        task_publish_retry_policy={"max_retries": 3, "interval_start": 0, "interval_step": 1, "interval_max": 3},
    )
    return app


# Explicit worker entrypoint: celery -A service.celery_app:app worker -Q kolovibe.identity
app = build_app()


@app.task(name="kolovibe.identity.event", ignore_result=True, autoretry_for=(DatabaseError,), retry_backoff=True,
          max_retries=10)
def receive_event(event_id, event_type, payload):
    """Apply an erasure confirmation once. Anything else is rejected, never acknowledged as handled."""
    import django
    django.setup()
    from .erasure import confirm
    from .events import ERASURE_CONFIRMED

    if event_type != ERASURE_CONFIRMED or not isinstance(payload, dict):
        raise ValueError("Unexpected Identity event")
    return confirm(event_id, payload)
