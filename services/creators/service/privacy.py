"""Decision C slice 2b: Creators erases one account's creator data (docs/privacy/account-erasure-plan-PROPOSED.md).

Run once per erasure request, through the idempotent inbox, in one transaction with its confirmation event:
- deleted: the creator application and the copyright review grant;
- the creator profile is deleted, unless enforcement measures point at it (`PROTECT`). Then the row is kept but
  de-identified: a meaningless handle, no name, location or bio, and status `suspended`, so it never shows again;
- de-identified: onboarding history, whose account link becomes one random tombstone for this erasure, so
  counts stay correct and nothing leads back to the person;
- retained, decision pending: measures, appeals and the append-only audit trail. Their retention is a policy
  decision (ADR-020), so they are reported as retained and the request stays open in Identity.
No constraint or append-only trigger is disabled. Nothing here reads another service's database; the confirmation
carries category names, counts and the creator profile id (an opaque identifier Moderation needs), nothing else.
"""
import uuid

from django.db import transaction
from django.db.models import Q

from .events import ERASURE_CONFIRMED, ERASURE_REQUESTED, SERVICE, accept_once, record_event
from .models import (AuditEvent, CopyrightReviewPolicy, CreatorApplication, CreatorProfile, CreatorRestriction,
                     OnboardingEvent, RestrictionAppeal)


def _request(payload):
    if (not isinstance(payload, dict) or set(payload) != {"request_id", "account_id", "service"}
            or payload["service"] != SERVICE):
        raise ValueError("Invalid erasure request")
    for key in ("request_id", "account_id"):
        if not isinstance(payload[key], str) or str(uuid.UUID(payload[key])) != payload[key]:
            raise ValueError("Invalid erasure request")
    return payload["request_id"], payload["account_id"]


def _profile(account_id, counts, retained):
    profile = CreatorProfile.objects.select_for_update().filter(user_id=account_id).first()
    counts["profile"] = counts["profile_deidentified"] = 0
    if profile is None:
        counts["copyright_review_grant"] = 0
        return None
    counts["copyright_review_grant"], _ = CopyrightReviewPolicy.objects.filter(creator=profile).delete()
    profile_id = profile.pk
    if not CreatorRestriction.objects.filter(creator=profile).exists():
        profile.delete()
        counts["profile"] = 1
        return profile_id
    CreatorProfile.objects.filter(pk=profile.pk).update(
        handle=f"erased-{profile_id.hex}", display_name="", location="", bio="",
        status=CreatorProfile.Status.SUSPENDED)
    counts["profile_deidentified"] = 1
    retained.append("measures")
    if RestrictionAppeal.objects.filter(restriction__creator=profile).exists():
        retained.append("appeals")
    return profile_id


def erase(event_id, payload):
    """Erase once and record the confirmation; a repeated delivery changes nothing and returns False."""
    request_id, account_id = _request(payload)
    with transaction.atomic():
        if not accept_once(event_id, ERASURE_REQUESTED):
            return False
        counts, retained = {}, []
        # The application points at the profile, so it goes first.
        counts["application"], _ = CreatorApplication.objects.filter(account_id=account_id).delete()
        profile_id = _profile(account_id, counts, retained)
        counts["onboarding_events_deidentified"] = OnboardingEvent.objects.filter(account_id=account_id).update(
            account_id=uuid.uuid4())
        subjects = [account_id] + ([profile_id] if profile_id else [])
        if AuditEvent.objects.filter(Q(actor_id=account_id) | Q(subject_id__in=subjects)).exists():
            retained.append("audit_events")
        # The profile id lets Identity ask Moderation for the decisions and strikes keyed by it.
        record_event(ERASURE_CONFIRMED, {"request_id": request_id, "account_id": account_id, "service": SERVICE,
                                         "creator_id": str(profile_id) if profile_id else None,
                                         "counts": counts, "retained": retained})
        return True
