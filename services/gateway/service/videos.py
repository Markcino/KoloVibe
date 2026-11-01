"""Public video read gateway; content remains the sole record owner."""

import json
import uuid
from urllib.error import HTTPError, URLError

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .internal_client import signed_internal_request


def _valid_item(item):
    if not isinstance(item, dict) or item.get("state") != "published":
        return False
    if not isinstance(item.get("title"), str) or not item["title"]:
        return False
    if not isinstance(item.get("id"), str) or not isinstance(item.get("creator_id"), str):
        return False
    try:
        uuid.UUID(item["id"])
        uuid.UUID(item["creator_id"])
    except (KeyError, TypeError, ValueError):
        return False
    return True


@require_GET
def list_videos(request):
    if set(request.GET) - {"creator_id", "cursor"}:
        return JsonResponse({"detail": "Invalid query"}, status=400)
    filters = {}
    for key in ("creator_id", "cursor"):
        value = request.GET.get(key)
        if value is not None:
            try:
                filters[key] = str(uuid.UUID(value))
            except ValueError:
                return JsonResponse({"detail": f"Invalid {key}"}, status=400)
    try:
        response = signed_internal_request(
            "content", "/internal/videos", method="POST",
            payload=json.dumps(filters, separators=(",", ":")).encode(),
        )
        with response:
            if response.status != 200:
                raise ValueError("Unexpected content response")
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Content response too large")
        result = json.loads(raw)
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("items"), list)
            or len(result["items"]) > 20
            or not all(_valid_item(item) for item in result["items"])
            or result.get("next_cursor") is not None
            and not isinstance(result["next_cursor"], str)
        ):
            raise ValueError("Invalid content response")
    except (HTTPError, URLError, TimeoutError, OSError, KeyError, ValueError, TypeError, UnicodeError):
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    return JsonResponse({"items": result["items"], "next_cursor": result.get("next_cursor")})


@require_GET
def video_detail(request, video_id):
    try:
        response = signed_internal_request(
            "content", "/internal/videos/detail", method="POST",
            payload=json.dumps({"video_id": str(video_id)}, separators=(",", ":")).encode(),
        )
        with response:
            if response.status != 200:
                raise ValueError("Unexpected content response")
            raw = response.read(8193)
        if len(raw) > 8192:
            raise ValueError("Content response too large")
        result = json.loads(raw)
        if not _valid_item(result) or result["id"] != str(video_id):
            raise ValueError("Invalid content response")
    except HTTPError as error:
        if error.code == 404:
            return JsonResponse({"detail": "Not found"}, status=404)
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    except (URLError, TimeoutError, OSError, KeyError, ValueError, TypeError, UnicodeError):
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    return JsonResponse(result)
