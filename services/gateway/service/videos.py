"""Public video read gateway; content remains the sole record owner."""

import json
import uuid
from urllib.error import HTTPError, URLError

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache

from .internal_client import signed_internal_request
from . import content_client, engagement_client
from .video_validation import CATEGORIES, valid_video


def _valid_item(item):
    try:
        return valid_video(item, public=True)
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def _with_likes(items):
    ids = [item["id"] for item in items]
    try:
        counts = engagement_client.like_counts(ids)
    except (OSError, RuntimeError, ValueError):
        counts = None
    if counts is not None and (
        not isinstance(counts, dict) or set(counts) != set(ids)
        or any(type(value) is not int or value < 0 for value in counts.values())
    ):
        raise ValueError("Invalid engagement counts")
    return [item | {"like_count": counts[item["id"]] if counts is not None else None} for item in items]


@never_cache
@require_GET
def list_videos(request):
    if (set(request.GET) - {"creator_id", "cursor", "q", "category", "sort"}
            or any(len(request.GET.getlist(key)) != 1 for key in request.GET)):
        return JsonResponse({"detail": "Invalid query"}, status=400)
    sort = request.GET.get("sort", "recent")
    category = request.GET.get("category")
    if sort not in {"recent", "trending"} or category is not None and category not in CATEGORIES:
        return JsonResponse({"detail": "Invalid query"}, status=400)
    if sort == "trending" and "cursor" in request.GET:
        return JsonResponse({"detail": "Trending does not accept a cursor"}, status=400)
    filters = {}
    if category is not None:
        filters["category"] = category
    query = request.GET.get("q")
    if query is not None:
        if not 1 <= len(query.strip()) <= 100 or any(ord(char) < 32 for char in query):
            return JsonResponse({"detail": "Invalid search query"}, status=400)
        filters["q"] = query.strip()
    for key in ("creator_id", "cursor"):
        value = request.GET.get(key)
        if value is not None:
            try:
                filters[key] = str(uuid.UUID(value))
            except ValueError:
                return JsonResponse({"detail": f"Invalid {key}"}, status=400)
    try:
        if sort == "trending":
            ids = engagement_client.trending_video_ids(20)
            if (not isinstance(ids, list) or len(ids) > 20 or len(set(ids)) != len(ids)
                    or any(not isinstance(value, str) or str(uuid.UUID(value)) != value for value in ids)):
                raise ValueError("Trending unavailable")
            items = content_client.lookup_public_videos(ids)
            if items is None:
                raise ValueError("Content lookup unavailable")
            items = [item for item in items
                     if (not filters.get("creator_id") or item["creator_id"] == filters["creator_id"])
                     and (category is None or item["category"] == category)
                     and (query is None or query.strip().casefold() in
                          (item["title"] + " " + item["description"]).casefold())]
            return JsonResponse({"items": _with_likes(items), "next_cursor": None})
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
        if category is not None and any(item["category"] != category for item in result["items"]):
            raise ValueError("Mismatched category filter")
        result["items"] = _with_likes(result["items"])
    except HTTPError as error:
        if error.code == 400:
            return JsonResponse({"detail": "Invalid query"}, status=400)
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    except (URLError, TimeoutError, OSError, KeyError, ValueError, TypeError, UnicodeError, RuntimeError):
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    return JsonResponse({"items": result["items"], "next_cursor": result.get("next_cursor")})


@never_cache
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
        result = _with_likes([result])[0]
    except HTTPError as error:
        if error.code == 404:
            return JsonResponse({"detail": "Not found"}, status=404)
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    except (URLError, TimeoutError, OSError, KeyError, ValueError, TypeError, UnicodeError, RuntimeError):
        return JsonResponse({"detail": "Content service unavailable"}, status=503)
    return JsonResponse(result)
