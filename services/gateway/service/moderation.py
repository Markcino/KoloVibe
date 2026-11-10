"""Authenticated gateway operations for the DEC-005 pilot."""

import json
import re
from urllib.error import HTTPError
from uuid import UUID

from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache

from .creator_onboarding import authenticated_actor, creator_ownership
from .internal_client import signed_internal_request


QUEUES = {"review_queue", "reports", "appeals"}
DECISIONS = {"video_decision", "report_decision", "appeal_decision"}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _valid_result(operation, result):
    if not isinstance(result, dict):
        return False
    if operation in QUEUES:
        if set(result) != {"items", "next_cursor"} or not isinstance(result["items"], list) or len(result["items"]) > 20:
            return False
        fields = {
            "review_queue": {"id", "title"},
            "reports": {"id", "video_id", "status", "created_at", "reason", "details"},
            "appeals": {"id", "video_id", "status", "created_at", "reason"},
        }[operation]
        return (all(isinstance(item, dict) and set(item) == fields
                    and all(isinstance(value, str) for value in item.values()) for item in result["items"])
                and (result["next_cursor"] is None or
                     bool(result["items"]) and result["items"][-1]["id"] == result["next_cursor"]))
    fields = ({"id", "video_id", "action", "status"} if operation in DECISIONS else
              {"id", "video_id", "status", "created_at"})
    return set(result) == fields and all(isinstance(value, str) for value in result.values())


def _forward(operation, actor, role, data):
    try:
        with signed_internal_request(
            "moderation", f"/internal/moderation/{operation}", method="POST", timeout=12,
            payload=json.dumps({"actor_id": actor, "role": role, "data": data}, ensure_ascii=False).encode(),
        ) as response:
            raw = response.read(524289)
            if len(raw) <= 524288 and response.status in (200, 201):
                result = json.loads(raw)
                if _valid_result(operation, result):
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
def moderation_endpoint(request, operation, target_id=None):
    method = "GET" if operation in QUEUES else "POST"
    if request.method != method:
        return HttpResponseNotAllowed([method])
    principal = authenticated_actor(request, require_verified_email=False)
    if isinstance(principal, JsonResponse):
        return principal
    actor, role = principal
    try:
        if operation in QUEUES:
            if request.body or set(request.GET) - {"cursor"} or len(request.GET.getlist("cursor")) > 1:
                raise ValueError("Invalid queue request")
            cursor = request.GET.get("cursor")
            data = {"cursor": str(UUID(cursor)) if cursor is not None else None}
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
                if set(data) != {"action", "reason"}:
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
    return _forward(operation, actor, role, data)
