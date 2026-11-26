"""RabbitMQ-backed Celery worker for Business: erasure requests (Decision C slice 2d).

Not imported by Django's HTTP settings. The worker needs an explicitly provisioned RabbitMQ account and verified TLS,
like the other services' workers. It reads its broker URI from settings (DJANGO_SETTINGS_MODULE must be set), so this
module touches neither the environment nor the file system. Business is not deployed to staging yet, so outside local
development the worker refuses to start until the owner approves a staging and broker plan.
"""
import ssl
from urllib.parse import urlsplit

from django.conf import settings
from django.db import DatabaseError

QUEUE = "kolovibe.business"


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
    if settings.ENVIRONMENT != "local":
        raise RuntimeError("Celery worker deployment is blocked until environment review")
    broker = validate_broker_url(settings.ERASURE_BROKER_URL)
    from celery import Celery

    app = Celery("kolovibe-business")
    app.conf.update(
        broker_url=broker, broker_use_ssl={"cert_reqs": ssl.CERT_REQUIRED},
        broker_connection_retry_on_startup=True, broker_transport_options={"confirm_publish": True},
        broker_heartbeat=30, task_default_queue=QUEUE, task_serializer="json", accept_content=["json"],
        result_backend=None, task_ignore_result=True, task_acks_late=True, task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1, task_publish_retry=True,
        task_publish_retry_policy={"max_retries": 3, "interval_start": 0, "interval_step": 1, "interval_max": 3},
    )
    return app


# Explicit worker entrypoint: celery -A service.celery_app:app worker -Q kolovibe.business
app = build_app()


@app.task(name="kolovibe.business.event", ignore_result=True, autoretry_for=(DatabaseError,), retry_backoff=True,
          max_retries=10)
def receive_event(event_id, event_type, payload):
    """Apply an erasure request once. Anything else is rejected, never acknowledged as handled."""
    import django
    django.setup()
    from .events import ERASURE_REQUESTED
    from .privacy import erase

    if event_type != ERASURE_REQUESTED or not isinstance(payload, dict):
        raise ValueError("Unexpected Business event")
    return erase(event_id, payload)
