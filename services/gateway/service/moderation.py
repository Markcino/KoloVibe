"""Authenticated gateway operations for the DEC-005 pilot."""

import json
import re
from urllib.error import HTTPError
from uuid import UUID

from django.http import HttpResponseNotAllowed, JsonResponse, HttpResponse
from django.views.decorators.cache import never_cache

from .creator_onboarding import authenticated_actor, creator_ownership
from .internal_client import signed_internal_request


DETAILS = {"video_detail", "report_detail", "appeal_detail"}

QUEUES = {"review_queue", "reports", "appeals"}
OWN_LISTS = {"own_reports", "own_appeals"}
OWN_DETAILS = {"own_report", "own_appeal"}
DECISIONS = {"video_decision", "report_decision", "appeal_decision"}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _valid_result(operation, result):
    if operation in DETAILS:
        from .reviewer_contracts import valid_detail
        return valid_detail(result)
    if operation in {"notice", "standing"}:
        from .standing import valid_notice
        if operation == "notice":
            return valid_notice(result)
        return (isinstance(result, dict) and set(result) == {"notices"} and isinstance(result["notices"], list)
                and len(result["notices"]) <= 20 and all(valid_notice(item) for item in result["notices"])
                and len({item["video_id"] for item in result["notices"]}) == len(result["notices"]))
    if not isinstance(result, dict):
        return False
    if operation in QUEUES | OWN_LISTS:
        if set(result) != {"items", "next_cursor"} or not isinstance(result["items"], list) or len(result["items"]) > 20:
            return False
        fields = {
            "review_queue": {"id", "title"},
            "reports": {"id", "video_id", "status", "created_at", "reason", "details"},
            "appeals": {"id", "video_id", "status", "created_at", "reason"},
            "own_reports": {"id", "video_id", "status", "created_at", "reason", "details"},
            "own_appeals": {"id", "video_id", "status", "created_at", "reason"},
        }[operation]
        return (all(isinstance(item, dict) and set(item) == fields
                    and all(isinstance(value, str) for value in item.values()) for item in result["items"])
                and (result["next_cursor"] is None or
                     bool(result["items"]) and result["items"][-1]["id"] == result["next_cursor"]))
    fields = ({"id", "video_id", "action", "status"} if operation in DECISIONS else
              {"id", "video_id", "status", "created_at", "reason", "details"} if operation == "own_report" else
              {"id", "video_id", "status", "created_at", "reason"} if operation == "own_appeal" else
              {"id", "video_id", "status", "created_at"})
    return set(result) == fields and all(isinstance(value, str) for value in result.values())


def _forward(operation, actor, role, data, *, mfa_verified=False):
    try:
        with signed_internal_request(
            "moderation", f"/internal/moderation/{operation}", method="POST", timeout=12,
            payload=json.dumps({"actor_id": actor, "role": role, "data": data}
                               | ({"mfa_verified": True} if mfa_verified else {}), ensure_ascii=False).encode(),
        ) as response:
            limit = 50 * 1024 * 1024 if operation == "preview" else 524288
            raw = response.read(limit + 1)
            if len(raw) <= limit and response.status in (200, 201):
                if operation == "preview":
                    if response.status != 200 or response.headers.get("Content-Type") != "video/mp4" or not raw:
                        raise ValueError
                    result = HttpResponse(raw, content_type="video/mp4")
                    result["Cache-Control"] = "private, no-store"
                    return result
                result = json.loads(raw)
                if _valid_result(operation, result):
                    return JsonResponse(result, status=response.status)
    except HTTPError as error:
        with error:
            if error.code in (400, 403, 404, 409):
                try:
                    raw = error.read(513)
                    result = json.loads(raw) if len(raw) <= 512 else None
                    if (error.code == 409 and operation == "report" and isinstance(result, dict)
                            and set(result) == {"detail", "code"} and isinstance(result["detail"], str)
                            and result["code"] == "already_reported"):
                        return JsonResponse(result, status=409)
                    if isinstance(result, dict) and set(result) == {"detail"} and isinstance(result["detail"], str):
                        return _error(result["detail"], error.code)
                except (OSError, ValueError, TypeError, AttributeError):
                    pass
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RuntimeError):
        pass
    return _error("Moderation temporarily unavailable", 503)


@never_cache
def moderation_endpoint(request, operation, target_id=None):
    method = "GET" if operation in QUEUES | OWN_LISTS | OWN_DETAILS | DETAILS | {"notice", "preview"} else "POST"
    if request.method != method:
        return HttpResponseNotAllowed([method])
    principal = authenticated_actor(request, require_verified_email=False)
    if isinstance(principal, JsonResponse):
        return principal
    actor, role = principal
    reviewer = operation in QUEUES | DECISIONS | DETAILS | {"preview"}
    if reviewer:
        if role not in {"moderator", "administrator"}:
            return _error("Reviewer role required", 403)
        from .standing import identity_context
        context = identity_context(request)
        if isinstance(context, JsonResponse):
            return context
        if context["account_id"] != actor or context["mfa_verified"] is not True:
            return _error("MFA-verified reviewer session required", 403)
    if operation == "notice":
        if role != "creator":
            return _error("Creator role required", 403)
        if request.GET or request.body:
            return _error("Invalid notice request", 400)
        ownership = creator_ownership(actor, role)
        if ownership.status_code != 200:
            return ownership
        result = _forward("notice", actor, role, {"video_id": str(target_id),
                          "creator_id": json.loads(ownership.content)["creator_id"]})
        if result.status_code == 200 and json.loads(result.content)["video_id"] != str(target_id):
            return _error("Moderation temporarily unavailable", 503)
        return result
    try:
        if operation in QUEUES | OWN_LISTS:
            if request.body or set(request.GET) - {"cursor"} or len(request.GET.getlist("cursor")) > 1:
                raise ValueError("Invalid queue request")
            cursor = request.GET.get("cursor")
            data = {"cursor": str(UUID(cursor)) if cursor is not None else None}
        elif operation in OWN_DETAILS | DETAILS | {"preview"}:
            if request.body or request.GET:
                raise ValueError("Invalid record request")
            data = {"preview_id" if operation == "preview" else "target_id": str(target_id)}
        else:
            if request.GET or len(request.body) > 32768:
                raise ValueError("Invalid moderation request")
            data = json.loads(request.body)
            if not isinstance(data, dict):
                raise ValueError("Invalid moderation request")
            if operation == "report":
                if not {"video_id", "reason"} <= set(data) or set(data) - {"video_id", "reason", "details"}:
                    raise ValueError("Invalid report")
                data.setdefault("details", "")
            elif operation in DECISIONS:
                if not {"action", "reason"} <= set(data) or set(data) - {"action", "reason", "reason_code"}:
                    raise ValueError("Invalid decision")
                data["target_id"] = str(target_id)
            elif set(data) != {"reason"}:
                raise ValueError("Invalid appeal")
            if operation == "report" or operation in DECISIONS:
                key = request.headers.get("Idempotency-Key", "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
                    raise ValueError("Invalid idempotency key")
                data["key"] = key
    except (ValueError, TypeError, AttributeError):
        return _error("Invalid moderation request", 400)

    if operation == "appeal":
        ownership = creator_ownership(actor, role)
        if ownership.status_code != 200:
            return ownership
        data.update(video_id=str(target_id), creator_id=json.loads(ownership.content)["creator_id"])
    return _forward(operation, actor, role, data, mfa_verified=reviewer)
