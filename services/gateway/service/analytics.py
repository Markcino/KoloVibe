"""Creator analytics composed from signed, service-owned reads."""

import json
from urllib.error import HTTPError

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .internal_client import signed_internal_request
from .media import _owned_creator


VIDEO_STATES = {"draft", "uploading", "processing", "failed", "review", "published", "rejected", "removed"}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _peer(service, path, payload):
    try:
        with signed_internal_request(service, path, method="POST", timeout=8,
                                     payload=json.dumps(payload, separators=(",", ":")).encode()) as response:
            raw = response.read(4097)
            if response.status == 200 and len(raw) <= 4096:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
    except HTTPError as error:
        with error:
            if error.code == 404:
                return None
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
        pass
    raise RuntimeError("Analytics service unavailable")


def _valid_count(value):
    return type(value) is int and value >= 0


@never_cache
@require_GET
def creator_analytics(request):
    creator_id, error = _owned_creator(request)
    if error is not None:
        return error
    if request.GET or request.body:
        return _error("Invalid analytics request", 400)
    try:
        result = _peer("content", "/internal/videos/analytics/summary", {"creator_id": creator_id})
        if (result is None or set(result) != {"total_videos", "videos_by_state"}
                or not _valid_count(result["total_videos"])
                or not isinstance(result["videos_by_state"], dict)
                or set(result["videos_by_state"]) != VIDEO_STATES
                or not all(_valid_count(value) for value in result["videos_by_state"].values())
                or result["total_videos"] != sum(result["videos_by_state"].values())):
            raise ValueError
        return JsonResponse(result)
    except (ValueError, TypeError, RuntimeError):
        return _error("Analytics temporarily unavailable", 503)


@never_cache
@require_GET
def creator_video_analytics(request, video_id):
    creator_id, error = _owned_creator(request)
    if error is not None:
        return error
    if request.GET or request.body:
        return _error("Invalid analytics request", 400)
    try:
        metadata = _peer("content", "/internal/videos/analytics/video",
                         {"creator_id": creator_id, "video_id": str(video_id)})
        if metadata is None:
            return _error("Video not found", 404)
        if set(metadata) != {"video_id", "state"} or metadata["video_id"] != str(video_id) or metadata["state"] not in VIDEO_STATES:
            raise ValueError
        counts = _peer("engagement", "/internal/engagement/analytics/video", {"video_id": str(video_id)})
        if (counts is None or set(counts) != {"video_id", "current_likes", "qualified_viewers"}
                or counts["video_id"] != str(video_id) or not _valid_count(counts["current_likes"])
                or not _valid_count(counts["qualified_viewers"])):
            raise ValueError
        return JsonResponse(metadata | {"current_likes": counts["current_likes"],
                                        "qualified_viewers": counts["qualified_viewers"]})
    except (ValueError, TypeError, RuntimeError):
        return _error("Analytics temporarily unavailable", 503)
