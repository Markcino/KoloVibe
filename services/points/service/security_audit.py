"""Transactional, immutable evidence, delivered separately from ledger work."""
from django.db import connection

from .models import AuditDelivery, AuditEvent

# Kinds this service emits today. points.reversed and points.adjusted are accepted
# by the audit service but have no ledger write path yet, so they are not emitted.
KINDS = {"points.awarded", "points.withheld"}


def record(kind, subject_id):
    if kind not in KINDS or not connection.in_atomic_block:
        raise RuntimeError("Points evidence requires its owning transaction")
    event = AuditEvent.objects.create(kind=kind, subject_id=subject_id)
    AuditDelivery.objects.create(event=event)
    return event
