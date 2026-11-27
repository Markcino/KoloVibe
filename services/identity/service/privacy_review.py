"""Decision C, first slice: administrator review of privacy requests, legal holds and account deactivation.

An administrator signed in with MFA lists requests, opens a review, declines with a fixed code, or approves a
deletion. Approval deactivates the account and revokes every session in the same transaction, so the person can no
longer sign in and no token keeps working. It does not erase anything yet: the other services' erasure, and the
request reaching `completed`, are the next slice, so an approved deletion stays `processing` until then. An access
request is approved with `approve-access`, which starts its export (`access_export`, mandate 3.3).

A hold (legal claim, authority request or fraud investigation) stops a deletion from being approved until an
administrator releases it. No retention period or hold duration is decided here (ADR-020 keeps them open).
Every operation records a security event; private notes never leave the console.
"""
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import access_export, erasure, events
from .accounts import _body, _error, _locked_account, _session_for_access
from .mfa import privileged_enabled
from .models import Account, AccountHold, LoginSession, PrivacyRequest
from .security_audit import record

FIELDS = {
    "list": {"status", "cursor"},
    "start-review": {"id"},
    "decline": {"id", "decline_code"},
    "approve-deletion": {"id"},
    "approve-access": {"id"},
    "holds": {"account_id"},
    "hold-place": {"account_id", "reason_code", "note"},
    "hold-release": {"id"},
}
PAGE = 50


def _actor(data, fresh):
    session = _session_for_access(data.get("access_token"))
    account = _locked_account(session) if session is not None else None
    if account is None:
        return None, _error("Invalid session", 401)
    if (account.role != Account.Role.ADMINISTRATOR or not privileged_enabled()
            or session.mfa_verified_at is None
            or fresh and session.mfa_verified_at <= timezone.now() - timedelta(minutes=5)):
        record("account.privacy_review_denied", account.id)
        return None, _error("Administrator sign-in within the last five minutes required", 403)
    return account, None


def _held(account_id):
    return AccountHold.objects.filter(account_id=account_id, released_at__isnull=True).exists()


def _erasure(item):
    """Each service's part of an approved deletion: whether it confirmed and the categories it kept. Category names
    only, so an administrator sees what the request is waiting on without any of the person's data."""
    order = {service: index for index, service in enumerate(events.ERASURE_SERVICES)}
    jobs = sorted(item.erasure_jobs.all(), key=lambda job: order.get(job.service, len(order)))
    return [{"service": job.service, "confirmed": job.confirmed_at is not None, "retained": list(job.retained)}
            for job in jobs]


def _export(item):
    """An access export's state for the console: when it was ready and which services it still waits on, never data."""
    export = getattr(item, "access_export", None) if item.kind == PrivacyRequest.Kind.ACCESS else None
    if export is None:
        return None
    return {"waiting_on": access_export.waiting_on(item), "ready_at": export.ready_at.isoformat() if export.ready_at
            else None, "expires_at": export.expires_at.isoformat() if export.expires_at else None,
            "purged": export.purged_at is not None, "retrievals": export.retrievals}


def request_row(item):
    return {"id": str(item.id), "account_id": str(item.account_id), "kind": item.kind, "status": item.status,
            "created_at": item.created_at.isoformat(),
            "review_started_at": item.review_started_at.isoformat() if item.review_started_at else None,
            "decided_at": item.decided_at.isoformat() if item.decided_at else None,
            "decline_code": item.decline_code or None, "held": _held(item.account_id),
            "erasure": _erasure(item), "export": _export(item)}


def hold_row(item):
    return {"id": str(item.id), "account_id": str(item.account_id), "reason_code": item.reason_code,
            "note": item.note, "placed_by": str(item.placed_by), "placed_at": item.placed_at.isoformat(),
            "released_at": item.released_at.isoformat() if item.released_at else None}


def _uuid_field(data, name):
    value = data.get(name)
    if not isinstance(value, str):
        raise ValueError
    return str(uuid.UUID(value))


def _parse(request):
    data = _body(request, {"access_token", "operation", *set().union(*FIELDS.values())})
    operation = data.get("operation")
    if operation not in FIELDS or set(data) - {"access_token", "operation"} - FIELDS[operation]:
        raise ValueError
    required = FIELDS[operation] - ({"status", "cursor"} if operation == "list" else set())
    if not required <= set(data):
        raise ValueError
    for name in {"id", "account_id", "cursor"} & set(data):
        data[name] = _uuid_field(data, name)
    if "status" in data and data["status"] not in PrivacyRequest.Status.values:
        raise ValueError
    if "decline_code" in data and data["decline_code"] not in PrivacyRequest.Decline.values:
        raise ValueError
    if "reason_code" in data and data["reason_code"] not in AccountHold.Reason.values:
        raise ValueError
    if "note" in data and (not isinstance(data["note"], str) or not 3 <= len(data["note"].strip()) <= 500):
        raise ValueError
    return operation, data


def _list(data):
    rows = PrivacyRequest.objects.order_by("-created_at", "-id")
    if data.get("status"):
        rows = rows.filter(status=data["status"])
    if data.get("cursor"):
        cursor = PrivacyRequest.objects.filter(pk=data["cursor"]).first()
        if cursor is None:
            return _error("Invalid cursor")
        rows = rows.filter(Q(created_at__lt=cursor.created_at) | Q(created_at=cursor.created_at, id__lt=cursor.id))
    page = list(rows.select_related("access_export").prefetch_related("erasure_jobs")[:PAGE + 1])
    return JsonResponse({"items": [request_row(item) for item in page[:PAGE]],
                         "next_cursor": str(page[PAGE - 1].id) if len(page) > PAGE else None})


def _request_for_update(data):
    return PrivacyRequest.objects.select_for_update().filter(pk=data["id"]).first()


def _conflict(detail, code):
    return JsonResponse({"detail": detail, "code": code}, status=409)


def _start_review(administrator, data, now):
    item = _request_for_update(data)
    if item is None:
        return _error("Request not found", 404)
    if item.status == PrivacyRequest.Status.IN_REVIEW:
        return JsonResponse(request_row(item))  # repeating the same step answers the same state
    if item.status != PrivacyRequest.Status.RECEIVED:
        return _conflict("This request is no longer waiting for review", "request_not_received")
    PrivacyRequest.objects.filter(pk=item.pk).update(
        status=PrivacyRequest.Status.IN_REVIEW, reviewed_by=administrator.id, review_started_at=now)
    record("account.privacy_review_started", administrator.id)
    item.refresh_from_db()
    return JsonResponse(request_row(item))


def _decline(administrator, data, now):
    item = _request_for_update(data)
    if item is None:
        return _error("Request not found", 404)
    if item.status == PrivacyRequest.Status.DECLINED and item.decline_code == data["decline_code"]:
        return JsonResponse(request_row(item))
    if item.status != PrivacyRequest.Status.IN_REVIEW:
        return _conflict("Only a request under review can be declined", "request_not_in_review")
    PrivacyRequest.objects.filter(pk=item.pk).update(
        status=PrivacyRequest.Status.DECLINED, decline_code=data["decline_code"], reviewed_by=administrator.id,
        decided_at=now)
    record("account.privacy_request_declined", administrator.id)
    item.refresh_from_db()
    return JsonResponse(request_row(item))


def _approve_deletion(administrator, data, now):
    item = _request_for_update(data)
    if item is None:
        return _error("Request not found", 404)
    if item.kind != PrivacyRequest.Kind.DELETION:
        return _conflict("Only a deletion request can be approved here", "request_not_deletion")
    if item.status == PrivacyRequest.Status.PROCESSING:
        return JsonResponse(request_row(item))
    if item.status != PrivacyRequest.Status.IN_REVIEW:
        return _conflict("Only a request under review can be approved", "request_not_in_review")
    if item.account_id == administrator.id:
        return _conflict("An administrator cannot approve the deletion of their own account", "own_account")
    account = Account.objects.select_for_update().get(pk=item.account_id)
    if AccountHold.objects.select_for_update().filter(account=account, released_at__isnull=True).exists():
        return _conflict("This account is on hold; release the hold before approving", "account_on_hold")
    PrivacyRequest.objects.filter(pk=item.pk).update(
        status=PrivacyRequest.Status.PROCESSING, reviewed_by=administrator.id, decided_at=now)
    account.is_active = False
    account.save(update_fields=["is_active"])
    LoginSession.objects.filter(account=account, revoked_at__isnull=True).update(revoked_at=now)
    erasure.open_jobs(item)
    record("account.privacy_deletion_approved", administrator.id)
    record("account.deactivated", account.id)
    item.refresh_from_db()
    return JsonResponse(request_row(item))


def _approve_access(administrator, data, now):
    """Approving an access request starts the export: Identity's part at once, a request to each service."""
    item = _request_for_update(data)
    if item is None:
        return _error("Request not found", 404)
    if item.kind != PrivacyRequest.Kind.ACCESS:
        return _conflict("Only an access request can be approved here", "request_not_access")
    if item.status in (PrivacyRequest.Status.PROCESSING, PrivacyRequest.Status.COMPLETED):
        return JsonResponse(request_row(item))
    if item.status != PrivacyRequest.Status.IN_REVIEW:
        return _conflict("Only a request under review can be approved", "request_not_in_review")
    try:
        access_export.retrieval_window()
    except access_export.NotConfigured:
        return _conflict("The export retrieval window is not configured", "export_window_not_configured")
    PrivacyRequest.objects.filter(pk=item.pk).update(
        status=PrivacyRequest.Status.PROCESSING, reviewed_by=administrator.id, decided_at=now)
    item.refresh_from_db()
    access_export.open_export(item, now)
    record("account.privacy_access_approved", administrator.id)
    item = PrivacyRequest.objects.get(pk=item.pk)
    return JsonResponse(request_row(item))


def _holds(data):
    if not Account.objects.filter(pk=data["account_id"]).exists():
        return _error("Account not found", 404)
    rows = AccountHold.objects.filter(account_id=data["account_id"]).order_by("-placed_at", "-id")[:PAGE]
    return JsonResponse({"items": [hold_row(item) for item in rows]})


def _place_hold(administrator, data, now):
    account = Account.objects.select_for_update().filter(pk=data["account_id"]).first()
    if account is None:
        return _error("Account not found", 404)
    existing = AccountHold.objects.filter(account=account, reason_code=data["reason_code"],
                                          released_at__isnull=True).first()
    if existing is not None:
        return JsonResponse(hold_row(existing))  # one open hold per reason
    item = AccountHold.objects.create(account=account, reason_code=data["reason_code"], note=data["note"].strip(),
                                      placed_by=administrator.id, placed_at=now)
    record("account.privacy_hold_placed", administrator.id)
    return JsonResponse(hold_row(item), status=201)


def _release_hold(administrator, data, now):
    item = AccountHold.objects.select_for_update().filter(pk=data["id"]).first()
    if item is None:
        return _error("Hold not found", 404)
    if item.released_at is None:
        AccountHold.objects.filter(pk=item.pk).update(released_by=administrator.id, released_at=now)
        record("account.privacy_hold_released", administrator.id)
        item.refresh_from_db()
    return JsonResponse(hold_row(item))


@never_cache
@require_POST
def administer(request):
    try:
        operation, data = _parse(request)
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        return _error("Invalid privacy review request")
    with transaction.atomic():
        administrator, error = _actor(data, fresh=operation not in {"list", "holds"})
        if error is not None:
            return error
        now = timezone.now()
        if operation == "list":
            record("account.privacy_requests_listed", administrator.id)
            return _list(data)
        if operation == "holds":
            record("account.privacy_requests_listed", administrator.id)
            return _holds(data)
        handler = {"start-review": _start_review, "decline": _decline, "approve-deletion": _approve_deletion,
                   "approve-access": _approve_access,
                   "hold-place": _place_hold, "hold-release": _release_hold}[operation]
        return handler(administrator, data, now)
