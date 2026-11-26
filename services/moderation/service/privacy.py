"""Decision C slice 2b: Moderation erases one account's data (docs/privacy/account-erasure-plan-PROPOSED.md).

Run once per erasure request, through the idempotent inbox, in one transaction with its confirmation event:
- de-identified: reports the person made, except copyright claims. The reporter becomes one random tombstone for
  this erasure. The free-text details are cleared unless a moderation decision cites the report, because then they
  are part of that decision's evidence and are retained pending a decision;
- revoked: a rights-holder verification. Its administrator-only evidence note is replaced with a fixed line, and
  `revoked_by` holds the erasure request id, since no administrator acts at that moment;
- deleted: reviewer previews; moderator assignments are deactivated;
- retained, decision pending: copyright claims and counter-notices (append-only by trigger), appeals, decisions,
  strikes, decisions the person took as staff, and the append-only audit trail. Their retention is a policy and
  copyright-counsel decision (ADR-020), so they are reported as retained and the request stays open in Identity.
No constraint or append-only trigger is disabled. Nothing here reads another service's database; the confirmation
carries category names and counts only.
"""
import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .events import ERASURE_CONFIRMED, ERASURE_REQUESTED, SERVICE, accept_once, record_event
from .models import (Appeal, AuditEvent, CopyrightStrike, CounterNotice, EditDecision, ModerationAction,
                     ModeratorAssignment, Report, ReviewerPreview, RightsHolder)

ERASED_EVIDENCE = "Removed when the account was erased (Decision C)."


def _request(payload):
    """Identity sends it after Creators confirmed, with the creator profile id (null for someone never a creator)."""
    if (not isinstance(payload, dict) or set(payload) != {"request_id", "account_id", "service", "creator_id"}
            or payload["service"] != SERVICE):
        raise ValueError("Invalid erasure request")
    for key in ("request_id", "account_id", "creator_id"):
        if key == "creator_id" and payload[key] is None:
            continue
        if not isinstance(payload[key], str) or str(uuid.UUID(payload[key])) != payload[key]:
            raise ValueError("Invalid erasure request")
    return payload["request_id"], payload["account_id"], payload["creator_id"]


def _reports(account_id, counts, retained):
    mine = Report.objects.filter(reporter_id=account_id)
    if mine.filter(copyrightnotice__isnull=False).exists():
        retained.append("copyright_claims")
    plain = mine.filter(copyrightnotice__isnull=True)
    cited = ModerationAction.objects.filter(report_id__in=plain.values("id")).values("report_id")
    if plain.filter(id__in=cited).exclude(details="").exists():
        retained.append("cited_report_details")
    tombstone = uuid.uuid4()
    cleared = plain.exclude(id__in=cited).update(reporter_id=tombstone, details="")
    counts["reports_deidentified"] = cleared + plain.filter(id__in=cited).update(reporter_id=tombstone)


def _rights_holder(account_id, request_id, counts):
    holder = RightsHolder.objects.select_for_update().filter(account_id=account_id).first()
    counts["rights_holder_revoked"] = 0
    if holder is None:
        return
    if holder.revoked_at is None:
        holder.revoked_by, holder.revoked_at = request_id, timezone.now()
        counts["rights_holder_revoked"] = 1
    holder.evidence = ERASED_EVIDENCE
    holder.save(update_fields=["revoked_by", "revoked_at", "evidence"])


def _retained(account_id, creator_id):
    # Decisions, edit decisions and strikes name the creator profile; appeals and counter-notices name the account.
    creator = [creator_id] if creator_id else []
    checks = {
        "counter_notices": CounterNotice.objects.filter(account_id=account_id),
        "appeals": Appeal.objects.filter(appellant_id=account_id),
        "decisions": ModerationAction.objects.filter(creator_id__in=creator),
        "edit_decisions": EditDecision.objects.filter(creator_id__in=creator),
        "strikes": CopyrightStrike.objects.filter(creator_id__in=creator),
        "staff_decisions": ModerationAction.objects.filter(reviewer_id=account_id),
        "staff_edit_decisions": EditDecision.objects.filter(reviewer_id=account_id),
        "audit_events": AuditEvent.objects.filter(Q(actor_id=account_id) | Q(subject_id=account_id)),
    }
    return [name for name, rows in checks.items() if rows.exists()]


def erase(event_id, payload):
    """Erase once and record the confirmation; a repeated delivery changes nothing and returns False."""
    request_id, account_id, creator_id = _request(payload)
    with transaction.atomic():
        if not accept_once(event_id, ERASURE_REQUESTED):
            return False
        counts, retained = {}, []
        _reports(account_id, counts, retained)
        _rights_holder(account_id, request_id, counts)
        counts["reviewer_previews"], _ = ReviewerPreview.objects.filter(actor_id=account_id).delete()
        counts["assignments_deactivated"] = ModeratorAssignment.objects.filter(
            moderator_id=account_id, active=True).update(active=False)
        retained += _retained(account_id, creator_id)
        record_event(ERASURE_CONFIRMED, {"request_id": request_id, "account_id": account_id, "service": SERVICE,
                                         "counts": counts, "retained": retained})
        return True
