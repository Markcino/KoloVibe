"""Decision E (D11-008): the Gateway boundary for verified rights holders.

Administrators only, with a live MFA-verified session. Verification marks a copyright claim for reviewers and
never decides one. Every Moderation answer is checked before it leaves.
"""

import json
from datetime import datetime
from urllib.error import HTTPError
from uuid import UUID

from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache

from .creator_onboarding import authenticated_actor
from .internal_client import signed_internal_request
from .responses import error_response as _error

ROW = {"account_id", "organisation", "evidence", "verified_by", "verified_at", "revoked_at", "active"}


def _uuid(value):
    return isinstance(value, str) and str(UUID(value)) == value


def _stamp(value):
    return isinstance(value, str) and len(value) <= 64 and datetime.fromisoformat(value).tzinfo is not None


def valid_row(item):
    try:
        return (isinstance(item, dict) and set(item) == ROW and _uuid(item["account_id"]) and _uuid(item["verified_by"])
                and item["account_id"] != item["verified_by"]
                and isinstance(item["organisation"], str) and 2 <= len(item["organisation"]) <= 200
                and isinstance(item["evidence"], str) and 10 <= len(item["evidence"]) <= 2000
                and _stamp(item["verified_at"]) and type(item["active"]) is bool
                and (item["revoked_at"] is None) == item["active"]
                and (item["revoked_at"] is None or _stamp(item["revoked_at"])))
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def _valid(operation, result, data):
    if operation == "rights-holders":
        if not isinstance(result, dict) or set(result) != {"items", "next_cursor"} or not isinstance(result["items"], list):
            return False
        ids = [item.get("account_id") if isinstance(item, dict) else None for item in result["items"]]
        return (len(ids) <= 20 and all(valid_row(item) for item in result["items"]) and ids == sorted(set(ids))
                and (data["cursor"] is None or all(item > data["cursor"] for item in ids))
                and (result["next_cursor"] is None or bool(ids) and result["next_cursor"] == ids[-1]))
    return (valid_row(result) and result["account_id"] == data["account_id"]
            and result["active"] is (operation == "rights-holder-verify"))


def forward(operation, actor, role, data):
    payload = json.dumps({"actor_id": actor, "role": role, "mfa_verified": True, "data": data},
                         separators=(",", ":")).encode()
    try:
        with signed_internal_request("moderation", f"/internal/moderation/{operation}", method="POST",
                                     payload=payload, timeout=12) as response:
            raw = response.read(262145)
            if len(raw) <= 262144 and response.status in (200, 201):
                result = json.loads(raw)
                if _valid(operation, result, data):
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
    return _error("Moderation temporarily unavailable", 503)


@never_cache
def rights_holders(request, operation, target_id=None):
    methods = ("GET", "POST") if operation == "rights-holders" else ("POST",)
    if request.method not in methods:
        return HttpResponseNotAllowed(methods)
    if operation == "rights-holders" and request.method == "POST":
        operation = "rights-holder-verify"
    actor = authenticated_actor(request, require_verified_email=False)
    if isinstance(actor, JsonResponse):
        return actor
    if actor[1] != "administrator":
        return _error("Administrator role required", 403)
    from .standing import identity_context
    context = identity_context(request)
    if isinstance(context, JsonResponse):
        return context
    if context["account_id"] != actor[0] or context["mfa_verified"] is not True:
        return _error("MFA-verified administrator session required", 403)
    try:
        if operation == "rights-holders":
            if request.body or set(request.GET) - {"cursor"} or len(request.GET.getlist("cursor")) > 1:
                raise ValueError
            cursor = request.GET.get("cursor")
            data = {"cursor": str(UUID(cursor)) if cursor is not None else None}
        else:
            if request.GET or len(request.body) > 8192:
                raise ValueError
            if operation == "rights-holder-revoke":
                if request.body:
                    raise ValueError
                data = {"account_id": str(target_id)}
            else:
                body = json.loads(request.body)
                if not isinstance(body, dict) or set(body) != {"account_id", "organisation", "evidence"}:
                    raise ValueError
                data = {"account_id": str(UUID(body["account_id"])), "organisation": body["organisation"],
                        "evidence": body["evidence"]}
    except (ValueError, TypeError, UnicodeError):
        return _error("Invalid rights holder request", 400)
    return forward(operation, *actor, data)
