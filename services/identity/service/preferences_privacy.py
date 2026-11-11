"""Identity-owned preferences and privacy request receipts.

No notification delivery or personal-data deletion is performed here.
"""

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .accounts import _body, _error, _session_for_access
from .models import Account, LoginSession, NotificationPreferences, PrivacyRequest
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
        data = _body(request, {"access_token", "operation", "kind", "current_password"})
        if data.get("operation") not in {"list", "create"}:
            raise ValueError
        if data["operation"] == "list":
            if set(data) != {"access_token", "operation"}:
                raise ValueError
        elif (set(data) != {"access_token", "operation", "kind", "current_password"}
              or data["kind"] not in PrivacyRequest.Kind.values
              or not isinstance(data["current_password"], str)
              or not 1 <= len(data["current_password"]) <= 128):
            raise ValueError
        session = _session_for_access(data["access_token"])
    except (ValueError, KeyError, TypeError):
        return _error("Invalid privacy request")
    if session is None:
        return _error("Unauthorized", 401)
    if data["operation"] == "list":
        rows = PrivacyRequest.objects.filter(account_id=session.account_id).order_by("created_at")
        return JsonResponse({"items": [_request(row) for row in rows]})
    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=session.account_id)
        active = LoginSession.objects.filter(
            pk=session.id, account_id=account.id, revoked_at__isnull=True).exists()
        if not active or not account.check_password(data["current_password"]):
            return _error("Reauthentication failed", 401)
        row, created = PrivacyRequest.objects.get_or_create(
            account_id=session.account_id, kind=data["kind"])
        if created:
            record("account.privacy_request_received", session.account_id)
    return JsonResponse(_request(row), status=201 if created else 200)
