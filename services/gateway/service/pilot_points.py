"""Signed Gateway routes for DEC-003 watch qualification and creator ledger reads."""

from datetime import datetime
import json
from urllib.error import HTTPError
from uuid import UUID

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .creator_onboarding import authenticated_actor, creator_ownership
from .creators import read_creator
from .internal_client import signed_internal_request


def error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _forward(service, path, payload, validate):
    try:
        with signed_internal_request(
            service, path, method="POST", payload=json.dumps(payload, separators=(",", ":")).encode(),
        ) as response:
            raw = response.read(16_385)
            if response.status == 200 and len(raw) <= 16_384:
                result = json.loads(raw)
                if isinstance(result, dict) and validate(result):
                    return JsonResponse(result)
    except HTTPError as failure:
        with failure:
            status = failure.code
            if status in (400, 403, 404, 409):
                return error({
                    400: "Invalid request", 403: "Forbidden",
                    404: "Not found", 409: "Watch session unavailable",
                }[status], status)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return error(f"{service.capitalize()} service unavailable", 503)


def _session(result):
    return (set(result) == {"session_id", "expires_at"}
            and str(UUID(result["session_id"])) == result["session_id"]
            and datetime.fromisoformat(result["expires_at"]).tzinfo is not None)


@never_cache
@require_POST
def watch(request, video_id=None):
    from .media import forward_media

    actor = authenticated_actor(request, require_verified_email=False)
    if isinstance(actor, JsonResponse):
        return actor
    if actor[1] not in ("viewer", "creator"):
        return error("Forbidden", 403)
    creating = video_id is not None
    try:
        if request.GET or len(request.body) > 512:
            raise ValueError
        if creating:
            if request.body:
                raise ValueError
            event = {}
        else:
            event = json.loads(request.body)
            if not isinstance(event, dict) or set(event) != {"video_id", "session_id", "position_ms"}:
                raise ValueError
            video_id = UUID(event.pop("video_id"))
            event["session_id"] = str(UUID(event["session_id"]))
            if type(event["position_ms"]) is not int or not 0 <= event["position_ms"] <= 300_000:
                raise ValueError
    except (ValueError, TypeError, AttributeError):
        return error("Invalid watch request", 400)
    asset = forward_media("watch" if creating else "watch-check", {"video_id": str(video_id)}, (200,))
    if asset.status_code != 200:
        return asset
    video = json.loads(asset.content)
    creator = read_creator(UUID(video["creator_id"]))
    if creator.status_code != 200:
        return creator
    creator_user_id = str(UUID(json.loads(creator.content)["user_id"]))
    if creator_user_id == actor[0]:
        return error("Self-views do not qualify", 403)
    payload = event | {
        "account_id": actor[0], "video_id": str(video_id), "creator_user_id": creator_user_id,
        "revision": video["revision"], "duration_ms": video["duration_ms"],
    }
    if creating:
        response = _forward("engagement", "/internal/engagement/watch/start", payload, _session)
        if response.status_code != 200:
            return response
        session = json.loads(response.content)
        return JsonResponse({
            "session_id": session["session_id"], "session_expires_at": session["expires_at"],
            "playback_url": video["playback_url"], "playback_expires_at": video["expires_at"],
        })
    return _forward("engagement", "/internal/engagement/watch/progress", payload,
                    lambda result: set(result) == {"qualified"} and type(result["qualified"]) is bool)


def _balance(result, creator_id):
    return (set(result) == {"creator_id", "balance", "currency", "as_of"}
            and result["creator_id"] == creator_id and result["currency"] == "POINTS"
            and type(result["balance"]) is int and datetime.fromisoformat(result["as_of"]).tzinfo is not None)


def _history(result, creator_id):
    if (set(result) != {"items", "next_cursor"} or not isinstance(result["items"], list)
            or len(result["items"]) > 20):
        return False
    for item in result["items"]:
        if (not isinstance(item, dict)
                or set(item) != {"id", "creator_id", "amount", "kind", "rule_version", "created_at"}
                or str(UUID(item["id"])) != item["id"] or item["creator_id"] != creator_id
                or type(item["amount"]) is not int or item["kind"] not in ("award", "reversal", "adjustment")
                or not isinstance(item["rule_version"], str) or not 1 <= len(item["rule_version"]) <= 32
                or datetime.fromisoformat(item["created_at"]).tzinfo is None):
            return False
    return (result["next_cursor"] is None
            or len(result["items"]) == 20 and result["next_cursor"] == result["items"][-1]["id"])


@never_cache
@require_GET
def creator_points(request, operation):
    actor = authenticated_actor(request, require_verified_email=True)
    if isinstance(actor, JsonResponse):
        return actor
    try:
        keys = {"cursor"} if operation == "entries" else set()
        if request.body or set(request.GET) - keys or len(request.GET.getlist("cursor")) > 1:
            raise ValueError
        cursor = request.GET.get("cursor")
        query = {"cursor": str(UUID(cursor)) if cursor is not None else None} if keys else {}
    except (ValueError, TypeError, AttributeError):
        return error("Invalid points query", 400)
    ownership = creator_ownership(*actor)
    if ownership.status_code != 200:
        return ownership
    creator_id = json.loads(ownership.content)["creator_id"]
    if creator_id is None:
        return error("Approved creator required", 403)
    validate = _history if operation == "entries" else _balance
    return _forward("points", f"/internal/points/{operation}",
                    query | {"account_id": actor[0], "creator_id": creator_id},
                    lambda result: validate(result, creator_id))
