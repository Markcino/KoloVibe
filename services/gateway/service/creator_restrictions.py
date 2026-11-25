"""Decision F (D-8): the Gateway boundary for creator measures, appeals and enforcement.

Administrators need a live MFA-verified session; creators act only on their own measures. Every Creators
answer is checked before it leaves. Enforcement reads (`capabilities`) are used by the media journey.
"""

import json
import re
from datetime import datetime
from urllib.error import HTTPError
from uuid import UUID

from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache

from .creator_onboarding import authenticated_actor
from .internal_client import signed_internal_request
from .responses import error_response as _error

KINDS = {"warning", "upload", "publishing", "monetization", "suspension"}
CODE = re.compile(r"[A-Z][A-Z0-9_]{1,63}")
VERSION = re.compile(r"[A-Za-z0-9._-]{1,32}")
KEY = re.compile(r"[A-Za-z0-9_-]{16,128}")
PUBLIC_FIELDS = {"id", "kind", "reason_code", "policy_version", "issued_at", "expires_at", "lifted_at", "active", "appeal"}
PRIVATE_FIELDS = PUBLIC_FIELDS | {"creator_id", "reason", "issued_by", "lifted_by", "lift_reason"}
ADMIN = {"issue", "lift", "list", "appeals", "decide"}


def _uuid(value, nullable=False):
    if value is None:
        return nullable
    return isinstance(value, str) and str(UUID(value)) == value


def _stamp(value, nullable=False):
    if value is None:
        return nullable
    return isinstance(value, str) and len(value) <= 64 and datetime.fromisoformat(value).tzinfo is not None


def _text(value, maximum=2000):
    return isinstance(value, str) and len(value) <= maximum


def valid_restriction(item, *, private):
    try:
        if not isinstance(item, dict) or set(item) != (PRIVATE_FIELDS if private else PUBLIC_FIELDS):
            return False
        appeal = item["appeal"]
        if not (_uuid(item["id"]) and item["kind"] in KINDS
                and isinstance(item["reason_code"], str) and CODE.fullmatch(item["reason_code"])
                and isinstance(item["policy_version"], str) and VERSION.fullmatch(item["policy_version"])
                and _stamp(item["issued_at"]) and _stamp(item["expires_at"], True) and _stamp(item["lifted_at"], True)
                and type(item["active"]) is bool and not (item["active"] and item["lifted_at"] is not None)
                and (appeal is None or isinstance(appeal, dict) and set(appeal) == {"id", "status"}
                     and _uuid(appeal["id"]) and appeal["status"] in {"open", "upheld", "lifted"})):
            return False
        if private:
            return (_uuid(item["creator_id"]) and _text(item["reason"]) and _uuid(item["issued_by"])
                    and _uuid(item["lifted_by"], True) and _text(item["lift_reason"])
                    and (item["lifted_by"] is None) == (item["lifted_at"] is None))
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def valid_appeal(item):
    try:
        return (isinstance(item, dict)
                and set(item) == {"id", "status", "created_at", "reason", "restriction", "decided_at", "decision_reason"}
                and _uuid(item["id"]) and item["status"] in {"open", "upheld", "lifted"} and _stamp(item["created_at"])
                and _text(item["reason"]) and _text(item["decision_reason"])
                and _stamp(item["decided_at"], nullable=True) and (item["status"] == "open") == (item["decided_at"] is None)
                and valid_restriction(item["restriction"], private=True))
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def _valid(operation, data, payload):
    if not isinstance(data, dict):
        return False
    if operation in {"issue", "lift"}:
        return (valid_restriction(data, private=True)
                and (operation != "issue" or data["creator_id"] == payload["creator_id"] and data["kind"] == payload["kind"])
                and (operation != "lift" or data["id"] == payload["restriction_id"] and data["lifted_at"] is not None))
    if operation == "list":
        return (set(data) == {"items"} and isinstance(data["items"], list) and len(data["items"]) <= 50
                and all(valid_restriction(item, private=True) and item["creator_id"] == payload["creator_id"]
                        for item in data["items"]))
    if operation == "mine":
        return (set(data) == {"creator_id", "items"} and _uuid(data["creator_id"], nullable=True)
                and isinstance(data["items"], list) and len(data["items"]) <= 50
                and all(valid_restriction(item, private=False) for item in data["items"]))
    if operation == "appeals":
        return (set(data) == {"items", "next_cursor"} and isinstance(data["items"], list) and len(data["items"]) <= 20
                and all(valid_appeal(item) for item in data["items"])
                and (data["next_cursor"] is None or bool(data["items"]) and data["next_cursor"] == data["items"][-1]["id"]))
    if operation == "decide":
        return valid_appeal(data) and data["id"] == payload["appeal_id"] and data["status"] != "open"
    if operation == "appeal":
        return set(data) == {"id", "status"} and _uuid(data["id"]) and data["status"] in {"open", "upheld", "lifted"}
    if operation == "capabilities":
        return (set(data) == {"creator_id", "upload", "publish", "monetization"} and _uuid(data["creator_id"], True)
                and all(type(data[name]) is bool for name in ("upload", "publish", "monetization"))
                and (data["creator_id"] is not None or not any(data[name] for name in ("upload", "publish", "monetization"))))
    return False


def forward(operation, actor, role, data):
    payload = json.dumps({"actor_id": actor, "role": role, "data": data}, separators=(",", ":")).encode()
    try:
        with signed_internal_request("creators", f"/internal/creators/restrictions/{operation}",
                                     method="POST", payload=payload) as response:
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
    return _error("Creator service unavailable", 503)


def capabilities(actor, role):
    """Decision F enforcement for the media journey: {creator_id, upload, publish, monetization} or an error."""
    return forward("capabilities", actor, role, {})


METHODS = {"admin_restrictions": ("GET", "POST"), "lift": ("POST",), "appeals": ("GET",), "decide": ("POST",),
           "mine": ("GET",), "appeal": ("POST",)}


def _body(request):
    if request.GET or len(request.body) > 8192:
        raise ValueError
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValueError
    return data


@never_cache
def creator_restrictions(request, operation, target_id=None):
    if request.method not in METHODS[operation]:
        return HttpResponseNotAllowed(METHODS[operation])
    if operation == "admin_restrictions":
        operation = "list" if request.method == "GET" else "issue"
    actor = authenticated_actor(request, require_verified_email=operation not in ADMIN)
    if isinstance(actor, JsonResponse):
        return actor
    if operation in ADMIN:
        if actor[1] != "administrator":
            return _error("Administrator role required", 403)
        from .standing import identity_context
        context = identity_context(request)
        if isinstance(context, JsonResponse):
            return context
        if context["account_id"] != actor[0] or context["mfa_verified"] is not True:
            return _error("MFA-verified administrator session required", 403)
    elif actor[1] not in {"viewer", "creator"}:
        return _error("Forbidden", 403)
    try:
        if operation in {"list", "mine"}:
            if request.GET or request.body:
                raise ValueError
            data = {"creator_id": str(target_id)} if operation == "list" else {}
        elif operation == "appeals":
            if request.body or set(request.GET) - {"cursor"} or len(request.GET.getlist("cursor")) > 1:
                raise ValueError
            cursor = request.GET.get("cursor")
            data = {"cursor": str(UUID(cursor)) if cursor is not None else None}
        else:
            body = _body(request)
            if operation == "issue":
                if set(body) != {"kind", "reason_code", "policy_version", "reason", "expires_at"}:
                    raise ValueError
                key = request.headers.get("Idempotency-Key", "")
                if not KEY.fullmatch(key):
                    raise ValueError
                data = {"creator_id": str(target_id), **body, "key": key}
            elif operation == "lift":
                if set(body) != {"reason"}:
                    raise ValueError
                data = {"restriction_id": str(target_id), "reason": body["reason"]}
            elif operation == "decide":
                if set(body) != {"decision", "reason"}:
                    raise ValueError
                data = {"appeal_id": str(target_id), **body}
            else:
                if set(body) != {"reason"}:
                    raise ValueError
                data = {"restriction_id": str(target_id), "reason": body["reason"]}
    except (ValueError, TypeError, UnicodeError):
        return _error("Invalid restriction request", 400)
    return forward(operation, *actor, data)
