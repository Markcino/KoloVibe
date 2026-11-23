"""Bind creator onboarding operations to the authenticated account at the gateway."""

import json
import re
from datetime import datetime
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


def _valid_pending(item):
    try:
        return (isinstance(item, dict) and set(item) == SUMMARY_FIELDS | {"handle", "submitted_at"}
                and _valid_summary({key: item[key] for key in SUMMARY_FIELDS}) and item["status"] == "pending"
                and isinstance(item["handle"], str) and re.fullmatch(r"[a-z0-9_]{3,30}", item["handle"]) is not None
                and isinstance(item["submitted_at"], str) and datetime.fromisoformat(item["submitted_at"]).tzinfo is not None)
    except (ValueError, TypeError, KeyError):
        return False


def _valid_response(operation, data, target):
    if operation == "review_policy":
        return (isinstance(data, dict) and set(data) == {"account_id", "creator_id", "trusted", "sample_percent", "policy_version"}
                and data["account_id"] == target and (data["creator_id"] is None or str(UUID(data["creator_id"])) == data["creator_id"])
                and type(data["trusted"]) is bool and type(data["sample_percent"]) is int and 0 <= data["sample_percent"] <= 100
                and (isinstance(data["policy_version"], str) and 1 <= len(data["policy_version"]) <= 32 if data["trusted"]
                     else data["sample_percent"] == 100 and data["policy_version"] is None))
    if operation == "ownership":
        return (isinstance(data, dict) and set(data) == {"creator_id"}
                and str(UUID(data["creator_id"])) == data["creator_id"])
    if operation == "eligibility":
        return (isinstance(data, dict) and set(data) == {"upload_eligible", "creator_id"}
                and type(data["upload_eligible"]) is bool
                and (str(UUID(data["creator_id"])) == data["creator_id"]
                     if data["upload_eligible"] else data["creator_id"] is None))
    if operation == "pending":
        return (isinstance(data, dict) and set(data) == {"items", "next_cursor"}
                and isinstance(data["items"], list) and len(data["items"]) <= 20
                and all(_valid_pending(item) for item in data["items"])
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


def authenticated_actor(request, *, require_verified_email):
    account = current_account(request, require_verified_email=require_verified_email)
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
    return actor, roles[0]


def creator_ownership(actor, role):
    return _forward("ownership", actor, role, {})


def synchronize_creator_role(account_id, *, expected_creator_id=None):
    """Only attest live, account-bound eligibility from the signed Creator peer.

    Repeatable after a partial review failure; Identity makes the grant idempotent.
    No public request fields are forwarded as an eligibility attestation.
    """
    eligibility = _forward("eligibility", account_id, "viewer", {})
    if eligibility.status_code != 200:
        return eligibility
    evidence = json.loads(eligibility.content)
    if not evidence["upload_eligible"]:
        return _error("Approved creator eligibility required", 403)
    if expected_creator_id is not None and evidence["creator_id"] != expected_creator_id:
        return _error("Creator service unavailable", 503)
    try:
        payload = {"account_id": account_id, **evidence}
        with signed_internal_request("identity", "/internal/auth/creator-role", method="POST",
                                     payload=json.dumps(payload).encode()) as response:
            raw = response.read(1025)
            if response.status != 200 or len(raw) > 1024:
                raise ValueError
        result = json.loads(raw)
        if (not isinstance(result, dict) or set(result) != {"account_id", "role", "changed"}
                or result["account_id"] != account_id or result["role"] != "creator"
                or type(result["changed"]) is not bool):
            raise ValueError
        return JsonResponse(result)
    except HTTPError as error:
        error.close()
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
        pass
    return _error("Creator access synchronization unavailable. Try again.", 503)


def reconcile_creator_access(actor):
    result = synchronize_creator_role(actor[0])
    if result.status_code != 200:
        return result
    # A concurrent reconciliation may have already revoked this request's session.
    # Always require a fresh sign-in when the authenticated role was viewer.
    return _error("Creator access updated. Sign in again.", 401)


def creator_eligibility(request):
    actor = authenticated_actor(request, require_verified_email=True)
    if isinstance(actor, JsonResponse):
        return actor
    if actor[1] == "viewer":
        eligibility = _forward("eligibility", *actor, {})
        if eligibility.status_code != 200 or not json.loads(eligibility.content)["upload_eligible"]:
            return eligibility
        return reconcile_creator_access(actor)
    return _forward("eligibility", *actor, {})


@never_cache
def creator_onboarding(request, operation, account_id=None):
    if request.method not in METHODS[operation]:
        return HttpResponseNotAllowed(METHODS[operation])
    if operation == "eligibility":
        if request.GET or request.body:
            return _error("Invalid creator request", 400)
        return creator_eligibility(request)
    actor = authenticated_actor(request, require_verified_email=operation in SELF_OPERATIONS)
    if isinstance(actor, JsonResponse):
        return actor

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
    result = _forward(operation, *actor, data)
    if operation == "review" and result.status_code == 200:
        application = json.loads(result.content)
        if application["status"] == "approved":
            sync = synchronize_creator_role(application["account_id"],
                                            expected_creator_id=application["creator_id"])
            if sync.status_code != 200:
                return sync
    return result
