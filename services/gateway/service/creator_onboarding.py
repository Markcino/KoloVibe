"""Bind creator onboarding operations to the authenticated account at the gateway."""

import json
from urllib.error import HTTPError
from uuid import UUID

from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache

from .accounts import current_account
from .internal_client import signed_internal_request


METHODS = {
    "invite": ("POST",), "pending": ("GET",), "review": ("POST",),
    "application": ("GET", "POST"), "eligibility": ("GET",),
}
SELF_OPERATIONS = {"application", "eligibility"}
SUMMARY_FIELDS = {"account_id", "status", "creator_id"}
STATUSES = {"invited", "pending", "approved", "rejected"}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _valid_summary(item, *, account_id=None):
    return (isinstance(item, dict) and set(item) == SUMMARY_FIELDS
            and isinstance(item["status"], str) and item["status"] in STATUSES
            and str(UUID(item["account_id"])) == item["account_id"]
            and (account_id is None or item["account_id"] == account_id)
            and (item["creator_id"] is None or str(UUID(item["creator_id"])) == item["creator_id"]))


def _valid_response(operation, data, target):
    if operation == "eligibility":
        return (isinstance(data, dict) and set(data) == {"upload_eligible", "creator_id"}
                and type(data["upload_eligible"]) is bool
                and (str(UUID(data["creator_id"])) == data["creator_id"]
                     if data["upload_eligible"] else data["creator_id"] is None))
    if operation == "pending":
        return (isinstance(data, dict) and set(data) == {"items", "next_cursor"}
                and isinstance(data["items"], list) and len(data["items"]) <= 20
                and all(_valid_summary(item) and item["status"] == "pending" for item in data["items"])
                and (data["next_cursor"] is None or
                     bool(data["items"]) and data["next_cursor"] == data["items"][-1]["account_id"]))
    return _valid_summary(data, account_id=target)


def _forward(operation, actor, role, data):
    payload = json.dumps({"actor_id": actor, "role": role, "data": data}, separators=(",", ":")).encode()
    target = data.get("account_id", actor)
    try:
        with signed_internal_request("creators", f"/internal/creators/onboarding/{operation}",
                                     method="POST", payload=payload) as response:
            raw = response.read(8193)
            if len(raw) <= 8192 and response.status in (200, 201):
                result = json.loads(raw)
                if _valid_response(operation, result, target):
                    return JsonResponse(result, status=response.status)
    except HTTPError as error:
        with error:
            if error.code in (400, 403, 404, 409):
                try:
                    raw = error.read(513)
                    result = json.loads(raw) if len(raw) <= 512 else None
                    if isinstance(result, dict) and set(result) == {"detail"} and isinstance(result["detail"], str):
                        return _error(result["detail"], error.code)
                except (OSError, ValueError, TypeError, AttributeError):
                    pass
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
        pass
    return _error("Creator service unavailable", 503)


@never_cache
def creator_onboarding(request, operation, account_id=None):
    if request.method not in METHODS[operation]:
        return HttpResponseNotAllowed(METHODS[operation])
    account = current_account(request, require_verified_email=operation in SELF_OPERATIONS)
    if account.status_code != 200:
        return account
    try:
        profile = json.loads(account.content)
        actor = str(UUID(profile["id"]))
        roles = profile["roles"]
        if len(roles) != 1:
            return _error("Forbidden", 403)
    except (ValueError, KeyError, TypeError, AttributeError):
        return _error("Identity unavailable", 503)

    try:
        if operation == "pending":
            if request.body or set(request.GET) - {"cursor"} or len(request.GET.getlist("cursor")) > 1:
                raise ValueError("Invalid query")
            cursor = request.GET.get("cursor")
            data = {"cursor": str(UUID(cursor)) if cursor is not None else None}
        else:
            if request.GET or len(request.body) > 256:
                raise ValueError("Invalid request")
            data = json.loads(request.body) if request.method == "POST" else {}
            if not isinstance(data, dict) or request.method == "GET" and request.body:
                raise ValueError("Invalid request")
            if operation == "invite":
                if set(data) != {"account_id"}:
                    raise ValueError("Invalid invitation")
                data["account_id"] = str(UUID(data["account_id"]))
            if operation == "review":
                if set(data) != {"decision"}:
                    raise ValueError("Invalid decision")
                data["account_id"] = str(account_id)
        if operation == "application":
            operation = "submit" if request.method == "POST" else "status"
    except (ValueError, TypeError, AttributeError):
        return _error("Invalid creator request", 400)
    return _forward(operation, actor, roles[0], data)
