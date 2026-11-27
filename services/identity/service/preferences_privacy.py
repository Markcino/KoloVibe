"""Identity-owned preferences and privacy request receipts.

No notification delivery or personal-data deletion is performed here; review is in privacy_review.py. The account
retrieves its own completed access export here (`export`), re-authenticated, until it expires (access_export.py).
"""
import uuid

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import access_export
from .accounts import (_body, _consume_reauthentication, _error, _locked_account,
                       _reauthenticate_password, _session_for_access)
from .models import NotificationPreferences, PrivacyRequest
from .security_audit import record


def _preferences(row):
    return {"email_notifications": row.email_notifications,
            "push_notifications": row.push_notifications}


def _request(row):
    return {"id": str(row.id), "kind": row.kind, "status": row.status,
            "created_at": row.created_at.isoformat()}


@require_POST
def preferences(request):
    try:
        data = _body(request, {"access_token", "operation", "email_notifications", "push_notifications"})
        if data.get("operation") not in {"get", "patch"}:
            raise ValueError
        if data["operation"] == "get":
            if set(data) != {"access_token", "operation"}:
                raise ValueError
        elif (set(data) != {"access_token", "operation", "email_notifications", "push_notifications"}
              or type(data["email_notifications"]) is not bool
              or type(data["push_notifications"]) is not bool):
            raise ValueError
        session = _session_for_access(data["access_token"])
    except (ValueError, KeyError, TypeError):
        return _error("Invalid preferences")
    if session is None:
        return _error("Unauthorized", 401)
    if data["operation"] == "get":
        row = NotificationPreferences.objects.filter(account_id=session.account_id).first()
        return JsonResponse(_preferences(row) if row else {
            "email_notifications": False, "push_notifications": False})
    with transaction.atomic():
        if _locked_account(session) is None:
            return _error("Unauthorized", 401)
        row, _ = NotificationPreferences.objects.select_for_update().get_or_create(
            account_id=session.account_id)
        row.email_notifications = data["email_notifications"]
        row.push_notifications = data["push_notifications"]
        row.save(update_fields=["email_notifications", "push_notifications", "updated_at"])
        record("account.preferences_updated", session.account_id)
    return JsonResponse(_preferences(row))


@require_POST
def privacy_requests(request):
    try:
        data = _body(request, {"access_token", "operation", "kind", "id", "current_password", "reauth_token"})
        if data.get("operation") not in {"list", "create", "export"}:
            raise ValueError
        if data["operation"] == "list":
            if set(data) != {"access_token", "operation"}:
                raise ValueError
        else:
            if data["operation"] == "create" and ("id" in data or data["kind"] not in PrivacyRequest.Kind.values):
                raise ValueError
            if data["operation"] == "export":
                # Retrieval of the account's own access export: the request id plus a fresh proof, like creation.
                if "kind" in data or not isinstance(data["id"], str):
                    raise ValueError
                data["id"] = str(uuid.UUID(data["id"]))
            if not {"current_password", "reauth_token"} & set(data):
                raise ValueError
            for field, minimum in (("current_password", 1), ("reauth_token", 32)):
                if field in data and (not isinstance(data[field], str)
                                      or not minimum <= len(data[field]) <= 128):
                    raise ValueError
        session = _session_for_access(data["access_token"])
    except (ValueError, KeyError, TypeError):
        return _error("Invalid privacy request")
    if session is None:
        return _error("Unauthorized", 401)
    if data["operation"] == "list":
        rows = PrivacyRequest.objects.filter(account_id=session.account_id).order_by("-created_at", "-id")[:40]
        return JsonResponse({"items": [_request(row) for row in rows]})
    with transaction.atomic():
        account = _locked_account(session)
        if account is None:
            return _error("Unauthorized", 401)
        if "reauth_token" in data:
            # A supplied token always takes precedence; never fall back after a bad proof.
            if not _consume_reauthentication(account, session, data["reauth_token"]):
                record("account.reauthentication_failed", account.id)
                return _error("Reauthentication failed")
        else:
            error = _reauthenticate_password(account, data["current_password"])
            if error is not None:
                return error
            record("account.reauthenticated", account.id)
        if data["operation"] == "export":
            status, body = access_export.retrieve(account, data["id"], timezone.now())
            if status != 200:
                record("account.privacy_export_denied", account.id)
            return JsonResponse(body, status=status)
        if PrivacyRequest.objects.filter(
            account=account, kind=data["kind"],
            status__in=PrivacyRequest.OPEN,
        ).exists():
            return JsonResponse({"detail": "An open request already exists", "code": "request_open"}, status=409)
        row = PrivacyRequest.objects.create(account=account, kind=data["kind"])
        record("account.privacy_request_received", account.id)
    return JsonResponse(_request(row), status=201)
