"""Decision C slice 2d: Business erases what needs no pending decision (docs/privacy/account-erasure-plan-PROPOSED.md).

Run once per erasure request, through the idempotent inbox, in one transaction with its confirmation event:
- deleted: the pilot registration grant;
- revoked: the person's staff memberships, the staff invitations they created that are still open, and their
  reviewer grants. The rows stay as history, as every revocation in this service does;
- retained, decision pending:
  - businesses the person owns (`business_ownership`): what happens to a business whose owner leaves is DR-BZ-08,
    and BZ-R-002 forbids removing the last owner except by closing the business;
  - reviews, inquiry threads and messages, and inquiry blocks (DR-BZ-25, already waiting on the owner);
  - verification cases, evidence and decisions, and profile revisions they submitted (retention period);
  - the append-only audit trail.
Idempotency records and throttle counters expire on their normal schedule. No constraint is disabled. Nothing here
reads another service's database; the confirmation carries category names and counts only.
"""
import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import authz
from .events import ERASURE_CONFIRMED, ERASURE_REQUESTED, SERVICE, accept_once, record_event
from .models import (AuditEvent, InquiryBlock, InquiryMessage, InquiryThread, ProfileRevision, RegistrationGrant,
                     Review, ReviewerGrant, StaffInvitation, VerificationCase, VerificationDecision)


def _request(payload):
    if (not isinstance(payload, dict) or set(payload) != {"request_id", "account_id", "service"}
            or payload["service"] != SERVICE):
        raise ValueError("Invalid erasure request")
    for key in ("request_id", "account_id"):
        if not isinstance(payload[key], str) or str(uuid.UUID(payload[key])) != payload[key]:
            raise ValueError("Invalid erasure request")
    return payload["request_id"], payload["account_id"]


def _retained(account_id):
    checks = {
        "business_ownership": authz.memberships_of(account_id).filter(role=authz.OWNER),
        "reviews": Review.objects.filter(author_account_id=account_id),
        "inquiries": InquiryThread.objects.filter(customer_account_id=account_id),
        "inquiry_messages": InquiryMessage.objects.filter(author_account_id=account_id),
        "inquiry_blocks": InquiryBlock.objects.filter(customer_account_id=account_id),
        "verification_evidence": VerificationCase.objects.filter(submitted_by_account_id=account_id),
        "verification_decisions": VerificationDecision.objects.filter(decided_by_account_id=account_id),
        "profile_revisions": ProfileRevision.objects.filter(
            Q(submitted_by_account_id=account_id) | Q(reviewed_by_account_id=account_id)),
        "audit_events": AuditEvent.objects.filter(Q(actor_id=account_id) | Q(subject_id=account_id)),
    }
    return [name for name, rows in checks.items() if rows.exists()]


def erase(event_id, payload):
    """Erase once and record the confirmation; a repeated delivery changes nothing and returns False."""
    request_id, account_id = _request(payload)
    with transaction.atomic():
        if not accept_once(event_id, ERASURE_REQUESTED):
            return False
        now = timezone.now()
        counts = {}
        counts["registration_grant"], _ = RegistrationGrant.objects.filter(account_id=account_id).delete()
        staff = list(authz.memberships_of(account_id).filter(role=authz.STAFF).select_for_update())
        for membership in staff:
            authz.revoke(membership)
        counts["staff_memberships_revoked"] = len(staff)
        counts["invitations_revoked"] = StaffInvitation.objects.filter(
            created_by_account_id=account_id, redeemed_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
        counts["reviewer_grants_deactivated"] = ReviewerGrant.objects.filter(
            reviewer_account_id=account_id, active=True).update(active=False)
        record_event(ERASURE_CONFIRMED, {"request_id": request_id, "account_id": account_id, "service": SERVICE,
                                         "counts": counts, "retained": _retained(account_id)})
        return True
