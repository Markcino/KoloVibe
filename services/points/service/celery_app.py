"""RabbitMQ-backed Celery worker bootstrap for the points service.

Not imported by Django's HTTP settings. Workers require an explicitly provisioned
RabbitMQ account and verified TLS. No production deployment is configured here.
"""
import os
import ssl
from urllib.parse import urlsplit

SERVICE = "points"
QUEUE = "kolovibe.points"


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
    """Initialize worker only for the existing local foundation environment."""
    if os.getenv("KOLOVIBE_ENV") != "local":
        raise RuntimeError("Celery worker deployment is blocked until environment review")
    broker = validate_broker_url(os.getenv("KOLOVIBE_RABBITMQ_URL", ""))

    # Imported only by the worker entrypoint. Celery must be added to the
    # existing hashed dependency lock before the worker can be shipped.
    from celery import Celery

    app = Celery("kolovibe-points")
    app.conf.update(
        broker_url=broker,
        broker_use_ssl={"cert_reqs": ssl.CERT_REQUIRED},
        broker_connection_retry_on_startup=True,
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


# Explicit worker entrypoint: celery -A service.celery_app:app worker -Q kolovibe.points
# HTTP service startup does not import this module.
app = build_app()
