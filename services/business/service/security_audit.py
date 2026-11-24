"""Transactional audit evidence, delivered separately (pattern: Moderation). Identifiers and decisions only."""
from django.db import connection

from .models import AuditDelivery, AuditEvent

KINDS = {"business.registered", "business.membership_granted", "business.membership_revoked",
         "business.invitation_created", "business.invitation_redeemed", "business.invitation_revoked",
         "business.registration_grant_changed",
         "business.reviewer_grant_changed", "business.verification_submitted", "business.verification_responded",
         "business.verification_claimed", "business.verification_decided", "business.verification_queue_read",
         "business.verification_case_read",
         "business.profile_edited", "business.profile_submitted", "business.profile_applied", "business.profile_decided",
         "business.profile_queue_read", "business.profile_revision_read", "business.hours_replaced",
         "business.category_changed", "business.listing_published", "business.listing_unpublished"}


def record(kind, actor_id, subject_type, subject_id):
    if kind not in KINDS or not connection.in_atomic_block:
        raise RuntimeError("Business evidence requires its owning transaction")
    event = AuditEvent.objects.create(kind=kind, actor_id=actor_id, subject_type=subject_type, subject_id=subject_id)
    AuditDelivery.objects.create(event=event)
    return event
