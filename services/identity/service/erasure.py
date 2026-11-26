"""Decision C slice 2a: erasure jobs and their confirmations (docs/privacy/account-erasure-plan-PROPOSED.md).

Approving a deletion opens one job per participating service and records one `privacy.erasure_requested` event per
job, in the same transaction that deactivates the account. Each service erases its own data and answers with
`privacy.erasure_confirmed`; `confirm` applies that answer once. A confirmation never completes the request on its
own: Identity's own de-identification and completion are a later slice, and a category reported as retained keeps
the request open until a retention decision exists.

Moderation keys a creator's decisions and strikes by the creator profile id, which only Creators knows, and Creators
deletes the profile while it erases. So Moderation's job opens with the others but its request is sent only when
Creators confirms, carrying the profile id Creators reported (or null when the person was never a creator).
"""
import re
import uuid

from django.db import transaction
from django.utils import timezone

from . import events
from .models import ErasureJob, PrivacyRequest
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
                or job.request.status != PrivacyRequest.Status.PROCESSING):
            raise ValueError("No open erasure job for this confirmation")
        if job.confirmed_at is None:
            job.confirmed_at = timezone.now()
            job.counts = payload["counts"]
            job.retained = payload["retained"]
            job.save(update_fields=["confirmed_at", "counts", "retained"])
            record("account.privacy_erasure_confirmed", job.request.account_id)
            if job.service == "creators":
                for service in events.AFTER_CREATORS:
                    _request(job.request, service, creator_id=payload["creator_id"])
        return True
