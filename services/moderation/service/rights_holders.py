"""Decision E (D11-008): administrators verify and revoke rights-holder accounts.

Verification is a signal for reviewers on a copyright claim. It never decides a claim, and the creator never sees
who claimed or for whom. Self-verification is refused.
"""
from uuid import UUID

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import RightsHolder
from .security_audit import record

PAGE = 20
FIELDS = {"rights-holders": {"cursor"}, "rights-holder-verify": {"account_id", "organisation", "evidence"},
          "rights-holder-revoke": {"account_id"}}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _text(value, minimum, maximum):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum or len(value) > maximum:
        raise ValueError("Invalid text")
    return value.strip()


def row(holder):
    return {"account_id": str(holder.account_id), "organisation": holder.organisation, "evidence": holder.evidence,
            "verified_by": str(holder.verified_by), "verified_at": holder.verified_at.isoformat(),
            "revoked_at": holder.revoked_at.isoformat() if holder.revoked_at else None,
            "active": holder.revoked_at is None}


def active(account_id):
    return RightsHolder.objects.filter(account_id=account_id, revoked_at__isnull=True).first()


def dispatch(operation, actor, data):
    if operation == "rights-holders":
        query = RightsHolder.objects.order_by("account_id")
        if data["cursor"] is not None:
            query = query.filter(account_id__gt=UUID(data["cursor"]))
        rows = list(query[:PAGE + 1])
        items = [row(holder) for holder in rows[:PAGE]]
        return JsonResponse({"items": items, "next_cursor": items[-1]["account_id"] if len(rows) > PAGE else None})
    account = UUID(data["account_id"])
    if account == actor:
        return _error("You cannot verify or revoke your own account", 403)
    with transaction.atomic():
        holder = RightsHolder.objects.select_for_update().filter(account_id=account).first()
        if operation == "rights-holder-verify":
            organisation = _text(data["organisation"], 2, 200)
            evidence = _text(data["evidence"], 10, 2000)
            if holder is not None and holder.revoked_at is None:
                if (holder.organisation, holder.evidence) != (organisation, evidence):
                    return _error("This account is already verified", 409)
                return JsonResponse(row(holder))
            holder, _ = RightsHolder.objects.update_or_create(account_id=account, defaults={
                "organisation": organisation, "evidence": evidence, "verified_by": actor,
                "verified_at": timezone.now(), "revoked_by": None, "revoked_at": None})
            record("moderation.rights_holder_verified", actor, "account", account)
            return JsonResponse(row(holder), status=201)
        if holder is None:
            return _error("Rights holder not found", 404)
        if holder.revoked_at is None:
            holder.revoked_by, holder.revoked_at = actor, timezone.now()
            holder.save(update_fields=["revoked_by", "revoked_at"])
            record("moderation.rights_holder_revoked", actor, "account", account)
        return JsonResponse(row(holder))
