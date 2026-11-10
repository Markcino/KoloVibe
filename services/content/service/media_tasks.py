"""Explicit local Celery/RabbitMQ worker for R2 media."""

import os
import ssl
from urllib.parse import urlsplit

from celery import Celery
from django.conf import settings
from django.db import DatabaseError

from . import media_encoding, media_storage


QUEUE = "kolovibe.content.media"


def _build_app():
    if not settings.LOCAL_MEDIA_ENABLED:
        raise RuntimeError("Local media processing is disabled")
    broker = os.environ.get("KOLOVIBE_RABBITMQ_URL", "")
    try:
        uri = urlsplit(broker)
        valid = (uri.scheme == "amqps" and uri.hostname and uri.username and uri.password
                 and uri.port in (None, 5671) and not uri.query and not uri.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise RuntimeError("Media worker requires an authenticated AMQPS broker")
    app = Celery("kolovibe-content-media", broker=broker)
    app.conf.update(
        broker_use_ssl={"cert_reqs": ssl.CERT_REQUIRED},
        broker_connection_retry_on_startup=True,
        broker_transport_options={"confirm_publish": True},
        broker_connection_timeout=5, broker_heartbeat=30,
        task_default_queue=QUEUE, task_serializer="json", accept_content=["json"],
        task_ignore_result=True, task_acks_late=True, task_reject_on_worker_lost=True,
        task_time_limit=240, worker_prefetch_multiplier=1,
    )
    return app


app = _build_app()


@app.task(bind=True, name="kolovibe.content.process_video", max_retries=12)
def process_video(self, video_id):
    from .media_processing import LeaseBusy, process

    try:
        process(video_id)
    except LeaseBusy:
        raise self.retry(countdown=60) from None
    except (media_storage.StorageUnavailable, media_encoding.EncoderUnavailable, DatabaseError, OSError):
        raise self.retry(countdown=min(30 * (self.request.retries + 1), 180)) from None
