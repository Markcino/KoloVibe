"""Public video read gateway; content remains the sole record owner."""

import json
import uuid
from datetime import datetime
from urllib.error import HTTPError, URLError

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .internal_client import signed_internal_request


def _valid_item(item):
    required = {"id", "creator_id", "title", "description", "state", "created_at"}
    if (not isinstance(item, dict) or not required <= item.keys()
            or item.keys() - required - {"duration_seconds"}
            or item.get("state") != "published"):
        return False
    if not isinstance(item["title"], str) or not 1 <= len(item["title"]) <= 160:
        return False
    if not isinstance(item["description"], str) or len(item["description"]) > 2000:
        return False
    if "duration_seconds" in item and (
        type(item["duration_seconds"]) is not int or item["duration_seconds"] < 0
    ):
        return False
    if not isinstance(item.get("id"), str) or not isinstance(item.get("creator_id"), str):
        return False
    try:
        uuid.UUID(item["id"])
        uuid.UUID(item["creator_id"])
        if datetime.fromisoformat(item["created_at"]).tzinfo is None:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


@require_GET
def list_videos(request):
    if (set(request.GET) - {"creator_id", "cursor"}
            or any(len(request.GET.getlist(key)) != 1 for key in request.GET)):
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
            or set(result) != {"items", "next_cursor"}
            or not isinstance(result.get("items"), list)
            or len(result["items"]) > 20
            or not all(_valid_item(item) for item in result["items"])
            or len({item["id"] for item in result["items"]}) != len(result["items"])
            or result["next_cursor"] is not None and (
                len(result["items"]) != 20
                or result["next_cursor"] != result["items"][-1]["id"])
        ):
            raise ValueError("Invalid content response")
        if filters.get("creator_id") and any(
            item["creator_id"] != filters["creator_id"] for item in result["items"]
        ):
            raise ValueError("Mismatched creator filter")
    except HTTPError as error:
        if error.code == 400:
            return JsonResponse({"detail": "Invalid query"}, status=400)
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    except (URLError, TimeoutError, OSError, KeyError, ValueError, TypeError, UnicodeError):
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    return JsonResponse({"items": result["items"], "next_cursor": result.get("next_cursor")})


@require_GET
def video_detail(request, video_id):
    return read_public_video(video_id)


def read_public_video(video_id):
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
