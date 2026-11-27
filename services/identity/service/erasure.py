"""Decision C: erasure jobs, their confirmations, and completion (docs/privacy/account-erasure-plan-PROPOSED.md).

Approving a deletion opens one job per participating service and records a `privacy.erasure_requested` event for
each that can start, in the same transaction that deactivates the account. Each service erases its own data and
answers with `privacy.erasure_confirmed`; `confirm` applies that answer once per event.

Moderation and Content key a creator's records by the creator profile id, which only Creators knows, and Creators
deletes the profile while it erases. So their jobs open with the others but their requests are sent only when
Creators confirms, carrying the profile id Creators reported (or null when the person was never a creator). Identity
keeps that id on the Creators job so `reapply` can send the same requests again.

Completion (slice 2e): once every job has confirmed and none retained a category, Identity de-identifies the account
row in the same transaction and the request becomes `completed`. A category reported as retained keeps the request
`processing`, which is the honest state while a retention decision is open, unless the owner-approved retention policy
(`retention_policy`) names it as evidence compatible with completion; the request then records that policy's id. A later confirmation of the same job
(from `reapply`, after a restore or once a decision lets a service erase more) replaces the earlier counts.
"""
import re
import uuid

from django.db import transaction
from django.utils import timezone

from . import events, retention_policy
from .models import (Account, EmailVerification, ErasureJob, LoginSession, MfaChallenge, NotificationPreferences,
                     PasswordReset, PrivacyRequest, RecoveryCode, TotpFactor)
from .security_audit import record

CATEGORY = re.compile(r"[a-z][a-z0-9_]{0,39}")


def _request(item, service, **extra):
    events.record_event(events.ERASURE_REQUESTED, {"request_id": str(item.id), "account_id": str(item.account_id),
                                                   "service": service, **extra})


def open_jobs(item):
    """Within the approving transaction: one job per participating service, and a request to each that can start."""
    for service in events.ERASURE_SERVICES:
        job, created = ErasureJob.objects.get_or_create(request=item, service=service)
        if created and service not in events.AFTER_CREATORS:
            _request(item, service)


def _uuid_or_none(value):
    return value is None or isinstance(value, str) and str(uuid.UUID(value)) == value


def valid_confirmation(payload):
    try:
        counts, retained = payload["counts"], payload["retained"]
        keys = {"request_id", "account_id", "service", "counts", "retained"}
        if payload["service"] == "creators":
            keys.add("creator_id")
        return (isinstance(payload, dict) and set(payload) == keys
                and _uuid_or_none(payload.get("creator_id"))
                and str(uuid.UUID(payload["request_id"])) == payload["request_id"]
                and str(uuid.UUID(payload["account_id"])) == payload["account_id"]
                and payload["service"] in events.ERASURE_SERVICES
                and isinstance(counts, dict) and len(counts) <= 20
                and all(isinstance(k, str) and CATEGORY.fullmatch(k) and type(v) is int and v >= 0
                        for k, v in counts.items())
                and isinstance(retained, list) and len(retained) <= 20
                and all(isinstance(k, str) and CATEGORY.fullmatch(k) for k in retained)
                and len(set(retained)) == len(retained))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def deidentify(account):
    """Within the completing transaction: keep the row (PROTECT references and append-only evidence point at it), but
    leave nothing that identifies the person or lets anyone sign in. Constraints and triggers stay as they are."""
    account.email = f"erased-{account.id.hex}@invalid"  # unique and undeliverable
    account.display_name = ""
    account.set_unusable_password()
    account.is_active = account.is_staff = False
    account.email_verified_at = None
    account.role = Account.Role.VIEWER
    account.save(update_fields=["email", "display_name", "password", "is_active", "is_staff", "email_verified_at",
                                "role"])
    account.groups.clear()
    account.user_permissions.clear()
    for model in (TotpFactor, RecoveryCode, MfaChallenge, EmailVerification, PasswordReset, NotificationPreferences,
                  LoginSession):  # sessions last: re-authentication and step-up proofs cascade with them
        model.objects.filter(account=account).delete()


def _complete_if_ready(item):
    jobs = list(ErasureJob.objects.filter(request=item))
    if {job.service for job in jobs} != set(events.ERASURE_SERVICES) or any(job.confirmed_at is None for job in jobs):
        return False
    policy = retention_policy.current() if any(job.retained for job in jobs) else retention_policy.EMPTY
    if any(retention_policy.blocking(job.service, job.retained, policy) for job in jobs):
        return False
    deidentify(Account.objects.select_for_update().get(pk=item.account_id))
    PrivacyRequest.objects.filter(pk=item.pk).update(
        status=PrivacyRequest.Status.COMPLETED,
        completed_under_policy=policy["policy_id"] if any(job.retained for job in jobs) else "")
    record("account.privacy_erasure_completed", item.account_id)
    return True


def confirm(event_id, payload):
    """Apply one confirmation exactly once. Returns False for a repeat; raises for an unknown job."""
    if not valid_confirmation(payload):
        raise ValueError("Invalid erasure confirmation")
    with transaction.atomic():
        if not events.accept_once(event_id, events.ERASURE_CONFIRMED):
            return False
        job = (ErasureJob.objects.select_for_update().select_related("request")
               .filter(request_id=payload["request_id"], service=payload["service"]).first())
        if (job is None or str(job.request.account_id) != payload["account_id"]
                or job.request.status not in (PrivacyRequest.Status.PROCESSING, PrivacyRequest.Status.COMPLETED)):
            raise ValueError("No erasure job for this confirmation")
        if job.request.status == PrivacyRequest.Status.COMPLETED:
            return True  # a re-applied erasure after a restore: the services erased again; nothing changes here
        first = job.confirmed_at is None
        job.confirmed_at = timezone.now()
        job.counts = payload["counts"]
        job.retained = payload["retained"]
        fields = ["confirmed_at", "counts", "retained"]
        if job.service == "creators" and first:
            job.creator_id = payload["creator_id"]
            fields.append("creator_id")
        job.save(update_fields=fields)
        record("account.privacy_erasure_confirmed", job.request.account_id)
        if job.service == "creators" and first:
            for service in events.AFTER_CREATORS:
                _request(job.request, service, creator_id=payload["creator_id"])
        _complete_if_ready(job.request)
        return True


def reapply(item):
    """Within a transaction: ask every participating service to erase this request's account again.

    For a restore (a restored service database no longer reflects an erasure it confirmed) or after a retention
    decision lets services erase more. Each service's erasure is idempotent, so a service with nothing left simply
    confirms again. Requests still waiting for Creators' first answer are left alone: that answer releases the rest.
    """
    if item.kind != PrivacyRequest.Kind.DELETION or item.status not in (PrivacyRequest.Status.PROCESSING,
                                                                       PrivacyRequest.Status.COMPLETED):
        return 0
    creators = ErasureJob.objects.filter(request=item, service="creators").first()
    if creators is None or creators.confirmed_at is None:
        return 0
    sent = 0
    for service in events.ERASURE_SERVICES:
        extra = {"creator_id": str(creators.creator_id) if creators.creator_id else None} \
            if service in events.AFTER_CREATORS else {}
        _request(item, service, **extra)
        sent += 1
    return sent
