"""Public own-account preferences and privacy receipt routes."""

import json
import re
from uuid import UUID

from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

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
            if set(data) != {"items"} or not isinstance(data["items"], list) or len(data["items"]) > 40:
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
            or item["status"] not in {"received", "in_review", "processing", "completed", "declined"}
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
            fields = _body(request, {"kind", "current_password", "reauth_token"})
            if (fields["kind"] not in {"access", "deletion"}
                    or not ({"reauth_token", "current_password"} & set(fields))):
                raise ValueError
            for field, minimum in (("current_password", 1), ("reauth_token", 32)):
                if field in fields and (not isinstance(fields[field], str)
                                        or not minimum <= len(fields[field]) <= 128):
                    raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeError):
            return _json({"detail": "Invalid privacy request"}, 400)
        data.update(operation="create", **fields)
        return _checked(_invoke("/internal/auth/privacy-requests", data, {201}), "receipt")
    return _checked(_invoke("/internal/auth/privacy-requests", data, {200}), "list")


EXPORT_SERVICES = {"identity", "engagement", "creators", "moderation", "content", "business"}
EXPORT_MAX_RESPONSE = 16 * 1024 * 1024  # a transport bound for an assembled export, not a policy value
EXPORT_CATEGORY = re.compile(r"[a-z][a-z0-9_]{0,39}")
SCALARS = (str, int, float, bool, type(None))


def _flat(value):
    """A row value is a scalar, or a list of scalars (a video's tags)."""
    return isinstance(value, SCALARS) or isinstance(value, list) and all(isinstance(item, SCALARS) for item in value)


def _names(value):
    return (isinstance(value, list) and len(value) <= 40 and len(set(value)) == len(value)
            and all(isinstance(name, str) and EXPORT_CATEGORY.fullmatch(name) for name in value))


def _valid_export(data):
    """The shape of an assembled export: per service, named categories of flat rows. The values are the person's own."""
    services = data["services"]
    return (set(data) == {"request_id", "generated_at", "expires_at", "services"}
            and str(UUID(data["request_id"])) == data["request_id"]
            and isinstance(data["generated_at"], str) and isinstance(data["expires_at"], str)
            and isinstance(services, dict) and set(services) <= EXPORT_SERVICES and "identity" in services
            and all(isinstance(part, dict) and set(part) == {"data", "withheld", "truncated"}
                    and isinstance(part["data"], dict) and _names(part["withheld"]) and _names(part["truncated"])
                    and all(EXPORT_CATEGORY.fullmatch(name) and isinstance(rows, list)
                            and all(isinstance(row, dict) and all(isinstance(key, str) and _flat(value)
                                                                  for key, value in row.items())
                                    for row in rows)
                            for name, rows in part["data"].items())
                    for part in services.values()))


@never_cache
@require_POST
def privacy_export(request, target_id):
    """The account's own completed access export, after a fresh re-authentication. Identity decides ownership,
    readiness and expiry (404, 409, 410); the answer is never cached."""
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    try:
        fields = _body(request, {"current_password", "reauth_token"})
        if not ({"reauth_token", "current_password"} & set(fields)):
            raise ValueError
        for field, minimum in (("current_password", 1), ("reauth_token", 32)):
            if field in fields and (not isinstance(fields[field], str) or not minimum <= len(fields[field]) <= 128):
                raise ValueError
    except (ValueError, KeyError, TypeError, UnicodeError):
        return _json({"detail": "Invalid export request"}, 400)
    result = _invoke("/internal/auth/privacy-requests",
                     {"access_token": token, "operation": "export", "id": str(target_id), **fields}, {200},
                     max_response=EXPORT_MAX_RESPONSE)
    if result.status_code != 200:
        return result
    try:
        valid = _valid_export(json.loads(result.content))
    except (ValueError, TypeError, KeyError, AttributeError):
        valid = False
    return result if valid else _json({"detail": "Identity unavailable"}, 503)
