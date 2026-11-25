"""Decision F (D-8): creator warnings, restrictions, suspensions, appeals and reinstatement.

Administrators issue and lift measures; a measure is lifted, and an appeal decided, only by an administrator
who did not issue it. The backend enforces each measure: upload and suspension stop new uploads, publishing and
suspension stop making videos public, and monetization and suspension stop future earnings eligibility.
Finance (Decision J) reads `monetization` for future earnings only; disputed and already-earned amounts are
Finance's to hold or release and are never changed here.
"""

import json
import re
from datetime import datetime
from uuid import UUID, uuid5

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import security_audit
from .models import CreatorProfile, CreatorRestriction as Restriction, RestrictionAppeal as Appeal

KINDS = set(Restriction.Kind.values)
BLOCKS = {"upload": {"upload", "suspension"}, "publish": {"publishing", "suspension"},
          "monetization": {"monetization", "suspension"}}
AUDIT = {"warning": "creator.warned", "suspension": "creator.suspended"}
PAGE_SIZE = 20
FIELDS = {
    "issue": {"creator_id", "kind", "reason_code", "policy_version", "reason", "expires_at", "key"},
    "lift": {"restriction_id", "reason"},
    "list": {"creator_id"},
    "appeals": {"cursor"},
    "decide": {"appeal_id", "decision", "reason"},
    "mine": set(), "appeal": {"restriction_id", "reason"}, "capabilities": set(),
}
ADMIN = {"issue", "lift", "list", "appeals", "decide"}
OWN = {"mine", "appeal", "capabilities"}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _text(value):
    if not isinstance(value, str) or not 10 <= len(value.strip()) <= 2000 or len(value) > 2000:
        raise ValueError("A reason of 10 to 2,000 characters is required")
    return value.strip()


def _code(value, pattern, maximum):
    if not isinstance(value, str) or not re.fullmatch(pattern, value) or len(value) > maximum:
        raise ValueError("Invalid code")
    return value


def active(creator_id, now=None):
    now = now or timezone.now()
    return Restriction.objects.filter(creator_id=creator_id, lifted_at__isnull=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def blocked(creator_id, capability):
    return active(creator_id).filter(kind__in=BLOCKS[capability]).exists()


def derived_status(profile):
    """Suspended, or restricted while publishing is blocked; otherwise the stored status.

    An upload-only or monetization-only measure leaves the public standing active: publishing stays allowed, and
    the Gateway's standing contract pairs "publishing allowed" with an active status.
    """
    kinds = set(active(profile.id).values_list("kind", flat=True))
    if "suspension" in kinds:
        return CreatorProfile.Status.SUSPENDED
    if "publishing" in kinds:
        return CreatorProfile.Status.RESTRICTED
    return profile.status


def _is_active(row, now):
    return row.lifted_at is None and (row.expires_at is None or row.expires_at > now)


def _row(row, *, private=False):
    now = timezone.now()
    appeal = getattr(row, "appeal", None)  # the reverse lookup raises AttributeError when there is none
    data = {"id": str(row.id), "kind": row.kind, "reason_code": row.reason_code, "policy_version": row.policy_version,
            "issued_at": row.issued_at.isoformat(), "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "lifted_at": row.lifted_at.isoformat() if row.lifted_at else None, "active": _is_active(row, now),
            "appeal": {"id": str(appeal.id), "status": appeal.status} if appeal else None}
    if private:
        data.update(creator_id=str(row.creator_id), reason=row.reason, issued_by=str(row.issued_by),
                    lifted_by=str(row.lifted_by) if row.lifted_by else None, lift_reason=row.lift_reason)
    return data


def _issue(actor, data):
    kind = data["kind"]
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("Invalid restriction kind")
    reason_code = _code(data["reason_code"], r"[A-Z][A-Z0-9_]{1,63}", 64)
    policy_version = _code(data["policy_version"], r"[A-Za-z0-9._-]{1,32}", 32)
    reason = _text(data["reason"])
    key = _code(data["key"], r"[A-Za-z0-9_-]{16,128}", 128)
    expires_at = data["expires_at"]
    now = timezone.now()
    if expires_at is not None:
        if not isinstance(expires_at, str) or len(expires_at) > 64:
            raise ValueError("Invalid expiry")
        expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None or expires_at <= now:
            raise ValueError("The expiry must be a future time with a time zone")
    creator_id = UUID(data["creator_id"])
    restriction_id = uuid5(actor, "restriction:" + key)
    with transaction.atomic():
        profile = CreatorProfile.objects.select_for_update().filter(pk=creator_id).first()
        if profile is None:
            return _error("Creator not found", 404)
        if profile.user_id == actor:
            return _error("Self-review is forbidden", 403)
        existing = Restriction.objects.filter(pk=restriction_id).first()
        if existing is not None:
            if (existing.creator_id, existing.kind, existing.reason_code, existing.policy_version, existing.reason,
                    existing.expires_at) != (creator_id, kind, reason_code, policy_version, reason, expires_at):
                return _error("Idempotency key already used", 409)
            return JsonResponse(_row(existing, private=True))
        row = Restriction.objects.create(id=restriction_id, creator=profile, kind=kind, reason_code=reason_code,
                                         policy_version=policy_version, reason=reason, issued_by=actor,
                                         issued_at=now, expires_at=expires_at)
        security_audit.record(AUDIT.get(kind, "creator.restricted"), actor, "creator", profile.id)
    return JsonResponse(_row(row, private=True), status=201)


def _lift(row, actor, reason):
    row.lifted_at, row.lifted_by, row.lift_reason = timezone.now(), actor, reason
    row.save(update_fields=["lifted_at", "lifted_by", "lift_reason"])
    security_audit.record("creator.restored", actor, "creator", row.creator_id)


def _lift_operation(actor, data):
    restriction_id, reason = UUID(data["restriction_id"]), _text(data["reason"])
    with transaction.atomic():
        row = Restriction.objects.select_for_update().filter(pk=restriction_id).first()
        if row is None:
            return _error("Restriction not found", 404)
        if row.lifted_at is not None:
            if (row.lifted_by, row.lift_reason) == (actor, reason):
                return JsonResponse(_row(row, private=True))  # a lost answer replays
            return _error("Restriction is already lifted", 409)
        if row.issued_by == actor:
            return _error("A different administrator must lift this measure", 403)
        if row.creator.user_id == actor:
            return _error("Self-review is forbidden", 403)
        _lift(row, actor, reason)
        # A lifted measure answers its open appeal too, so the queue never holds a moot appeal.
        Appeal.objects.filter(restriction=row, status=Appeal.Status.OPEN).update(
            status=Appeal.Status.LIFTED, decided_by=actor, decided_at=row.lifted_at, decision_reason=reason)
    return JsonResponse(_row(Restriction.objects.select_related("appeal").get(pk=row.pk), private=True))


def _list(data):
    rows = Restriction.objects.select_related("appeal").filter(creator_id=UUID(data["creator_id"])).order_by("-issued_at", "-id")[:50]
    return JsonResponse({"items": [_row(row, private=True) for row in rows]})


def _appeal_row(appeal):
    row = appeal.restriction
    return {"id": str(appeal.id), "status": appeal.status, "created_at": appeal.created_at.isoformat(),
            "reason": appeal.reason, "restriction": _row(row, private=True),
            "decided_at": appeal.decided_at.isoformat() if appeal.decided_at else None,
            "decision_reason": appeal.decision_reason}


def _appeals(data):
    query = Appeal.objects.select_related("restriction").filter(status=Appeal.Status.OPEN).order_by("id")
    if data["cursor"] is not None:
        query = query.filter(id__gt=UUID(data["cursor"]))
    rows = list(query[:PAGE_SIZE + 1])
    items = [_appeal_row(row) for row in rows[:PAGE_SIZE]]
    return JsonResponse({"items": items, "next_cursor": items[-1]["id"] if len(rows) > PAGE_SIZE else None})


def _decide(actor, data):
    decision, reason = data["decision"], _text(data["reason"])
    if decision not in {"uphold", "lift"}:
        raise ValueError("Invalid appeal decision")
    with transaction.atomic():
        appeal = Appeal.objects.select_for_update().select_related("restriction", "restriction__creator").filter(
            pk=UUID(data["appeal_id"])).first()
        if appeal is None:
            return _error("Appeal not found", 404)
        status = Appeal.Status.LIFTED if decision == "lift" else Appeal.Status.UPHELD
        if appeal.status != Appeal.Status.OPEN:
            if (appeal.status, appeal.decided_by, appeal.decision_reason) == (status, actor, reason):
                return JsonResponse(_appeal_row(appeal))
            return _error("Appeal is already decided", 409)
        row = appeal.restriction
        if actor in (row.issued_by, appeal.appellant_id, row.creator.user_id):
            return _error("An independent administrator must decide this appeal", 403)
        appeal.status, appeal.decided_by, appeal.decided_at, appeal.decision_reason = status, actor, timezone.now(), reason
        appeal.save(update_fields=["status", "decided_by", "decided_at", "decision_reason"])
        security_audit.record("creator.restriction_appeal_decided", actor, "creator", row.creator_id)
        if decision == "lift" and row.lifted_at is None:
            _lift(row, actor, reason)
    return JsonResponse(_appeal_row(appeal))


def _mine(actor):
    profile = CreatorProfile.objects.filter(user_id=actor).first()
    if profile is None:
        return JsonResponse({"creator_id": None, "items": []})
    rows = Restriction.objects.select_related("appeal").filter(creator=profile).order_by("-issued_at", "-id")[:50]
    return JsonResponse({"creator_id": str(profile.id), "items": [_row(row) for row in rows]})


def _appeal(actor, data):
    reason = _text(data["reason"])
    with transaction.atomic():
        row = Restriction.objects.select_for_update().select_related("creator").filter(
            pk=UUID(data["restriction_id"]), creator__user_id=actor).first()
        if row is None:
            return _error("Restriction not found", 404)
        appeal = Appeal.objects.filter(restriction=row).first()
        if appeal is not None:
            if (appeal.appellant_id, appeal.reason) == (actor, reason):
                return JsonResponse({"id": str(appeal.id), "status": appeal.status})
            return _error("An appeal already exists for this measure", 409)
        if not _is_active(row, timezone.now()):
            return _error("This measure no longer applies", 409)
        appeal = Appeal.objects.create(id=uuid5(row.id, "appeal"), restriction=row, appellant_id=actor, reason=reason)
        security_audit.record("creator.restriction_appealed", actor, "creator", row.creator_id)
    return JsonResponse({"id": str(appeal.id), "status": appeal.status}, status=201)


def _capabilities(actor):
    """Each capability needs an approved creator (the onboarding rules) and no active measure that blocks it."""
    from .onboarding import approved_profile
    profile = CreatorProfile.objects.filter(user_id=actor).first()
    if profile is None:
        return JsonResponse({"creator_id": None, "upload": False, "publish": False, "monetization": False})
    approved = approved_profile(actor) is not None
    kinds = set(active(profile.id).values_list("kind", flat=True))
    return JsonResponse({"creator_id": str(profile.id),
                         **{name: approved and not kinds & blocks for name, blocks in BLOCKS.items()}})


@require_POST
def restrictions(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return _error("Forbidden", 403)
    try:
        if len(request.body) > 8192:
            raise ValueError("Request too large")
        envelope = json.loads(request.body)
        if not isinstance(envelope, dict) or set(envelope) != {"actor_id", "role", "data"}:
            raise ValueError("Invalid envelope")
        actor, role, data = UUID(envelope["actor_id"]), envelope["role"], envelope["data"]
        if operation not in FIELDS or not isinstance(data, dict) or set(data) != FIELDS[operation]:
            raise ValueError("Invalid restriction operation")
        if operation in ADMIN and role != "administrator":
            return _error("Forbidden", 403)
        if operation in OWN and role not in {"viewer", "creator"}:
            return _error("Forbidden", 403)
        handlers = {"issue": lambda: _issue(actor, data), "lift": lambda: _lift_operation(actor, data),
                    "list": lambda: _list(data), "appeals": lambda: _appeals(data),
                    "decide": lambda: _decide(actor, data), "mine": lambda: _mine(actor),
                    "appeal": lambda: _appeal(actor, data), "capabilities": lambda: _capabilities(actor)}
        return handlers[operation]()
    except (ValueError, TypeError, AttributeError, KeyError):
        return _error("Invalid restriction request", 400)
    except IntegrityError:
        return _error("Restriction conflicts with an existing record", 409)
    except DatabaseError:
        return _error("Creator service unavailable", 503)
