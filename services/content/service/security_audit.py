"""Transactional, immutable video evidence, delivered to Audit separately from the business work (D11-007)."""
from django.db import connection

from .models import AuditDelivery, AuditEvent

# Exactly the vocabulary the Audit service accepts from this producer (services/audit/service/events.py).
KINDS = {"video.created", "video.updated", "video.upload_intent_created", "video.upload_completed",
         "video.processing_succeeded", "video.processing_failed", "video.deleted", "video.published",
         "video.unpublished", "video.moderated", "video.edit_submitted", "video.edit_withdrawn",
         "video.edit_approved", "video.edit_rejected"}


def record(kind, video_id, actor_id=None):
    if kind not in KINDS or not connection.in_atomic_block:
        raise RuntimeError("Video evidence requires a known kind and its owning transaction")
    event = AuditEvent.objects.create(kind=kind, actor_id=actor_id, subject_type="video", subject_id=video_id)
    AuditDelivery.objects.create(event=event)
    return event
