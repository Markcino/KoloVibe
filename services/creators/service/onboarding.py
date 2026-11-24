"""Creator-owned DEC-004 pilot invitation, review and eligibility transitions."""

import json
import re
from uuid import UUID

from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import CreatorApplication as Application, CreatorProfile, CopyrightReviewPolicy, OnboardingEvent


POLICY_VERSION = "DEC-004-pilot-v1"
REVIEWER_ROLES = {"moderator", "administrator"}
ADMIN_OPERATIONS = {"outstanding", "revoke"}  # least privilege: only administrators see or withdraw invitations
APPLICANT_ROLES = {"viewer", "creator"}
PAGE_SIZE = 20


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _summary(application):
    return {"account_id": str(application.account_id), "status": application.status,
            "creator_id": str(application.profile_id) if application.profile_id else None}


def _record(account_id, actor, action):
    OnboardingEvent.objects.create(account_id=account_id, actor_id=actor, action=action)


def _invite(actor, role, account_id):
    if actor == account_id:
        return _error("Self-review is forbidden", 403)
    with transaction.atomic():
        application, created = Application.objects.select_for_update().get_or_create(
            account_id=account_id, defaults={"invited_by": actor},
        )
        if created:
            _record(account_id, actor, OnboardingEvent.Action.INVITED)
        elif application.status == Application.Status.REVOKED:
            # Undoing a withdrawal is as privileged as making it.
            if role != "administrator":
                return _error("Forbidden", 403)
            application.status = Application.Status.INVITED
            application.invited_by = actor
            application.invited_at = timezone.now()
            application.reviewed_by = None
            application.reviewed_at = None
            application.save(update_fields=["status", "invited_by", "invited_at", "reviewed_by", "reviewed_at"])
            _record(account_id, actor, OnboardingEvent.Action.REINVITED)
    return JsonResponse(_summary(application), status=201 if created else 200)


def _revoke(actor, account_id):
    """invited -> revoked only. A submitted application is decided by review; a decided one is never undone here."""
    if actor == account_id:
        return _error("Self-review is forbidden", 403)
    with transaction.atomic():
        application = Application.objects.select_for_update().filter(account_id=account_id).first()
        if application is None:
            return _error("Creator invitation not found", 404)
        if application.status == Application.Status.REVOKED:
            return JsonResponse(_summary(application))  # repeat is a no-op: one event per revocation
        if application.status != Application.Status.INVITED:
            return _error("Only an outstanding invitation can be revoked", 409)
        application.status = Application.Status.REVOKED
        application.reviewed_by = actor
        application.reviewed_at = timezone.now()
        application.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        _record(account_id, actor, OnboardingEvent.Action.REVOKED)
    return JsonResponse(_summary(application))


def _outstanding(cursor):
    query = Application.objects.filter(status=Application.Status.INVITED).order_by("account_id")
    if cursor is not None:
        query = query.filter(account_id__gt=UUID(cursor))
    applications = list(query[:PAGE_SIZE + 1])
    items = [{**_summary(application), "invited_at": application.invited_at.isoformat()}
             for application in applications[:PAGE_SIZE]]
    return JsonResponse({"items": items,
                         "next_cursor": items[-1]["account_id"] if len(applications) > PAGE_SIZE else None})


def _submit(actor, data):
    if data["adult_attested"] is not True or data["rights_attested"] is not True:
        return _error("Both pilot attestations are required", 400)
    handle = data["handle"]
    if not isinstance(handle, str) or not re.fullmatch(r"[a-z0-9_]{3,30}", handle):
        return _error("Invalid creator handle", 400)

    with transaction.atomic():
        application = Application.objects.select_for_update().filter(account_id=actor).first()
        if application is None or application.status == Application.Status.REVOKED:
            return _error("Creator invitation required", 403)
        if application.status == Application.Status.PENDING and application.profile.handle.lower() == handle.lower():
            return JsonResponse(_summary(application))
        if application.status != Application.Status.INVITED:
            return _error("Creator application cannot be changed", 409)

        profile = CreatorProfile.objects.select_for_update().filter(user_id=actor).first()
        if profile is None:
            handle = handle.lower()
            if CreatorProfile.objects.filter(handle__iexact=handle).exists():
                return _error("Creator handle is unavailable", 409)
            profile = CreatorProfile.objects.create(user_id=actor, handle=handle, display_name=handle)
        elif (profile.handle.lower() != handle.lower() or profile.restricted_at is not None
              or profile.status not in (CreatorProfile.Status.PENDING, CreatorProfile.Status.ACTIVE)):
            return _error("Existing creator profile cannot be changed by onboarding", 409)

        application.profile = profile
        application.status = Application.Status.PENDING
        application.attestation_version = POLICY_VERSION
        application.submitted_at = timezone.now()
        application.save(update_fields=["profile", "status", "attestation_version", "submitted_at"])
    return JsonResponse(_summary(application), status=201)


def _review(actor, account_id, decision):
    if actor == account_id:
        return _error("Self-review is forbidden", 403)
    if decision not in (Application.Status.APPROVED, Application.Status.REJECTED):
        return _error("Invalid creator review decision", 400)
    with transaction.atomic():
        application = Application.objects.select_for_update().filter(account_id=account_id).first()
        if application is None:
            return _error("Creator application not found", 404)
        if application.status == decision and application.reviewed_by == actor:
            return JsonResponse(_summary(application))
        if application.status != Application.Status.PENDING:
            return _error("Creator application is not pending", 409)
        if decision == Application.Status.APPROVED:
            profile = CreatorProfile.objects.select_for_update().get(pk=application.profile_id)
            if (application.attestation_version != POLICY_VERSION or profile.restricted_at is not None
                    or profile.status not in (CreatorProfile.Status.PENDING, CreatorProfile.Status.ACTIVE)):
                return _error("Creator profile cannot be approved", 409)
            if profile.status == CreatorProfile.Status.PENDING:
                profile.status = CreatorProfile.Status.ACTIVE
                profile.reviewed_at = timezone.now()
                profile.save(update_fields=["status", "reviewed_at"])
        application.status = decision
        application.reviewed_by = actor
        application.reviewed_at = timezone.now()
        application.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        _record(account_id, actor, decision)
    return JsonResponse(_summary(application))


def _pending(cursor):
    query = Application.objects.filter(status=Application.Status.PENDING).order_by("account_id")
    if cursor is not None:
        query = query.filter(account_id__gt=UUID(cursor))
    applications = list(query.select_related("profile")[:PAGE_SIZE + 1])
    items = [{**_summary(application), "handle": application.profile.handle,
              "submitted_at": application.submitted_at.isoformat()} for application in applications[:PAGE_SIZE]]
    return JsonResponse({"items": items,
                         "next_cursor": items[-1]["account_id"] if len(applications) > PAGE_SIZE else None})


def _status(actor, operation):
    if operation == "review_policy":
        eligibility = json.loads(_status(actor, "eligibility").content)
        policy = CopyrightReviewPolicy.objects.filter(creator_id=eligibility["creator_id"], active=True).first() if eligibility["upload_eligible"] else None
        trusted = bool(policy and policy.approved_by != actor and policy.approved_at <= timezone.now()
                       and policy.version.strip() and policy.reason.strip())
        return JsonResponse({"account_id": str(actor), "creator_id": eligibility["creator_id"],
            "trusted": trusted, "sample_percent": policy.sample_percent if trusted else 100,
            "policy_version": policy.version if trusted else None})
    if operation == "standing":
        profile = CreatorProfile.objects.filter(user_id=actor).first()
        eligible = (profile is not None and profile.status == CreatorProfile.Status.ACTIVE
                    and profile.reviewed_at is not None and profile.restricted_at is None
                    and Application.objects.filter(account_id=actor, profile=profile,
                        status=Application.Status.APPROVED, attestation_version=POLICY_VERSION).exists())
        return JsonResponse({"creator_id": str(profile.id) if profile else None,
                             "creator_status": profile.status if profile else None,
                             "publishing_allowed": eligible})
    if operation == "ownership":
        profile_id = CreatorProfile.objects.filter(user_id=actor).values_list("id", flat=True).first()
        if profile_id is None:
            return _error("Creator profile not found", 404)
        return JsonResponse({"creator_id": str(profile_id)})
    application = Application.objects.select_related("profile").filter(account_id=actor).first()
    if operation == "eligibility":
        eligible = (
            application is not None and application.status == Application.Status.APPROVED
            and application.attestation_version == POLICY_VERSION and application.profile is not None
            and application.profile.user_id == actor
            and application.profile.status == CreatorProfile.Status.ACTIVE
            and application.profile.reviewed_at is not None and application.profile.restricted_at is None
        )
        return JsonResponse({"upload_eligible": eligible,
                             "creator_id": str(application.profile_id) if eligible else None})
    if application is None or application.status == Application.Status.REVOKED:
        return _error("Creator application not found", 404)  # a withdrawn invitation looks like none to the applicant
    return JsonResponse(_summary(application))


@require_POST
def onboarding(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return _error("Forbidden", 403)
    try:
        if len(request.body) > 512:
            raise ValueError("Request too large")
        envelope = json.loads(request.body)
        if not isinstance(envelope, dict) or set(envelope) != {"actor_id", "role", "data"}:
            raise ValueError("Invalid envelope")
        actor, role, data = UUID(envelope["actor_id"]), envelope["role"], envelope["data"]
        if not isinstance(role, str) or not isinstance(data, dict):
            raise ValueError("Invalid envelope")
        required = {
            "invite": {"account_id"}, "pending": {"cursor"}, "outstanding": {"cursor"}, "revoke": {"account_id"}, "review": {"account_id", "decision"},
            "submit": {"handle", "adult_attested", "rights_attested"}, "status": set(), "eligibility": set(), "ownership": set(), "standing": set(), "review_policy": set(),
        }
        if operation not in required or set(data) != required[operation]:
            raise ValueError("Invalid creator operation")
        allowed = (APPLICANT_ROLES | REVIEWER_ROLES if operation == "standing" else {"administrator"} if operation in ADMIN_OPERATIONS
                   else REVIEWER_ROLES if operation in ("invite", "pending", "review") else APPLICANT_ROLES)
        if role not in allowed:
            return _error("Forbidden", 403)
        if operation == "invite":
            return _invite(actor, role, UUID(data["account_id"]))
        if operation == "revoke":
            return _revoke(actor, UUID(data["account_id"]))
        if operation == "outstanding":
            return _outstanding(data["cursor"])
        if operation == "submit":
            return _submit(actor, data)
        if operation == "review":
            return _review(actor, UUID(data["account_id"]), data["decision"])
        if operation == "pending":
            return _pending(data["cursor"])
        return _status(actor, operation)
    except (ValueError, TypeError, AttributeError, KeyError):
        return _error("Invalid creator request", 400)
    except IntegrityError:
        return _error("Creator application conflicts with an existing record", 409)
    except DatabaseError:
        return _error("Creator service unavailable", 503)


def eligibility(request):
    """The upload-eligibility check alone, pinned to its operation; same caller, envelope and role checks."""
    return onboarding(request, "eligibility")


def ownership(request):
    """The account-to-creator ownership lookup alone, pinned to its operation; same caller, envelope and role checks.

    The account is always the envelope's authenticated actor; the request carries no other account identifier.
    """
    return onboarding(request, "ownership")
