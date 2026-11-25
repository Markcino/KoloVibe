"""Transactional, immutable creator evidence, delivered to Audit separately from the business work (D11-007)."""
from django.db import connection

from .models import AuditDelivery, AuditEvent

# Exactly the vocabulary the Audit service accepts from this producer (services/audit/service/events.py).
KINDS = {"creator.invited", "creator.invitation_revoked", "creator.application_submitted", "creator.approved",
         "creator.rejected", "creator.profile_updated"}
SUBJECT_TYPES = {"account", "creator"}


def record(kind, actor_id, subject_type, subject_id):
    if kind not in KINDS or subject_type not in SUBJECT_TYPES or not connection.in_atomic_block:
        raise RuntimeError("Creator evidence requires a known kind and its owning transaction")
    event = AuditEvent.objects.create(kind=kind, actor_id=actor_id, subject_type=subject_type, subject_id=subject_id)
    AuditDelivery.objects.create(event=event)
    return event
