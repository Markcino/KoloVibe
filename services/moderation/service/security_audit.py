"""Transactional, immutable evidence, delivered separately from business work."""
from django.db import connection
from .models import AuditDelivery, AuditEvent

KINDS = {"moderation.report_created", "moderation.appeal_created", "moderation.decision_recorded",
         "moderation.decision_applied", "moderation.decision_conflicted", "moderation.assignment_denied"}


def record(kind, actor_id, subject_type, subject_id):
    if kind not in KINDS or not connection.in_atomic_block:
        raise RuntimeError("Moderation evidence requires its owning transaction")
    event = AuditEvent.objects.create(kind=kind, actor_id=actor_id,
                                     subject_type=subject_type, subject_id=subject_id)
    AuditDelivery.objects.create(event=event)
    return event
