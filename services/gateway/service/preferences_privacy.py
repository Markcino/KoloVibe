"""Public own-account preferences and privacy receipt routes."""

import json
from uuid import UUID

from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .accounts import _bearer, _body, _invoke, _json


def _checked(result, kind):
    if result.status_code not in {200, 201}:
        return result
    try:
        data = json.loads(result.content)
        if kind == "preferences":
            if (set(data) != {"email_notifications", "push_notifications"}
                    or any(type(value) is not bool for value in data.values())):
                raise ValueError
        elif kind == "list":
            if set(data) != {"items"} or not isinstance(data["items"], list) or len(data["items"]) > 2:
                raise ValueError
            data = {"items": [_checked_receipt(item) for item in data["items"]]}
        else:
            data = _checked_receipt(data)
    except (ValueError, TypeError, KeyError, AttributeError):
        return _json({"detail": "Identity unavailable"}, 503)
    return _json(data, result.status_code)


def _checked_receipt(item):
    if (not isinstance(item, dict) or set(item) != {"id", "kind", "status", "created_at"}
            or item["kind"] not in {"access", "deletion"}
            or item["status"] != "received"
            or not isinstance(item["created_at"], str)
            or len(item["created_at"]) > 64):
        raise ValueError
    UUID(item["id"])
    return item


@never_cache
@require_http_methods(["GET", "PATCH"])
def preferences(request):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    data = {"access_token": token, "operation": "get"}
    if request.method == "PATCH":
        try:
            fields = _body(request, {"email_notifications", "push_notifications"})
            if (set(fields) != {"email_notifications", "push_notifications"}
                    or type(fields["email_notifications"]) is not bool
                    or type(fields["push_notifications"]) is not bool):
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeError):
            return _json({"detail": "Invalid preferences"}, 400)
        data.update(operation="patch", **fields)
    return _checked(_invoke("/internal/auth/preferences", data, {200}), "preferences")


@never_cache
@require_http_methods(["GET", "POST"])
def privacy_requests(request):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    data = {"access_token": token, "operation": "list"}
    if request.method == "POST":
        try:
            fields = _body(request, {"kind", "current_password"})
            if (set(fields) != {"kind", "current_password"}
                    or fields["kind"] not in {"access", "deletion"}
                    or not isinstance(fields["current_password"], str)
                    or not 1 <= len(fields["current_password"]) <= 128):
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeError):
            return _json({"detail": "Invalid privacy request"}, 400)
        data.update(operation="create", **fields)
        return _checked(_invoke("/internal/auth/privacy-requests", data, {200, 201}), "receipt")
    return _checked(_invoke("/internal/auth/privacy-requests", data, {200}), "list")
