"""Creator analytics composed from signed, service-owned reads."""

from datetime import date, timedelta
import json
import math
from uuid import UUID
from urllib.error import HTTPError

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .internal_client import signed_internal_request
from .accounts import current_account
from .video_validation import valid_video
from .media import _owned_creator


VIDEO_STATES = {"draft", "uploading", "processing", "failed", "review", "published", "rejected", "removed"}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _peer(service, path, payload):
    try:
        with signed_internal_request(service, path, method="POST", timeout=8,
                                     payload=json.dumps(payload, separators=(",", ":")).encode()) as response:
            raw = response.read(65537)
            if response.status == 200 and len(raw) <= 65536:
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


def _range(request, choices):
    if (request.body or set(request.GET) - {"range"} or len(request.GET.getlist("range")) > 1):
        raise ValueError
    value = request.GET.get("range", "7d")
    if value not in choices:
        raise ValueError
    return value


def _seconds(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _valid_metrics(data):
    return (all(_valid_count(data.get(name)) for name in ("qualified_plays", "likes", "shares"))
            and _seconds(data.get("watch_time_seconds"))
            and data["watch_time_seconds"] <= data["qualified_plays"] * 300)


def _valid_summary(data, creator_id, user_id, period):
    fields = {"creator_id", "creator_user_id", "range", "qualified_plays", "watch_time_seconds",
              "likes", "new_followers", "shares", "daily", "top_videos"}
    if (not isinstance(data, dict) or set(data) != fields or data["creator_id"] != creator_id
            or data["creator_user_id"] != user_id or data["range"] != period
            or not _valid_metrics(data) or not _valid_count(data["new_followers"])
            or not isinstance(data["daily"], list) or len(data["daily"]) not in (0, 7 if period == "7d" else 28)
            or not isinstance(data["top_videos"], list) or len(data["top_videos"]) > 5):
        return False
    dates = []
    for row in data["daily"]:
        if (not isinstance(row, dict) or set(row) != {"date", "qualified_plays", "likes"}
                or not isinstance(row["date"], str) or len(row["date"]) != 10
                or not _valid_count(row["qualified_plays"]) or not _valid_count(row["likes"])):
            return False
        dates.append(date.fromisoformat(row["date"]))
    if any(after - before != timedelta(days=1) for before, after in zip(dates, dates[1:])):
        return False
    if (sum(row["qualified_plays"] for row in data["daily"]) != data["qualified_plays"]
            or sum(row["likes"] for row in data["daily"]) != data["likes"]):
        return False
    ranks = []
    for row in data["top_videos"]:
        if (not isinstance(row, dict) or set(row) != {"video_id", "qualified_plays"}
                or not isinstance(row["video_id"], str) or str(UUID(row["video_id"])) != row["video_id"]
                or not _valid_count(row["qualified_plays"]) or not 1 <= row["qualified_plays"] <= data["qualified_plays"]):
            return False
        ranks.append((-row["qualified_plays"], row["video_id"]))
    return (ranks == sorted(ranks) and len({key[1] for key in ranks}) == len(ranks)
            and sum(-key[0] for key in ranks) <= data["qualified_plays"])


@never_cache
@require_GET
def creator_analytics(request):
    creator_id, error = _owned_creator(request)
    if error is not None:
        return error
    try:
        period = _range(request, {"7d", "28d"})
    except ValueError:
        return _error("Invalid analytics request", 400)
    identity = current_account(request)
    if identity.status_code != 200:
        return identity
    try:
        user_id = str(UUID(json.loads(identity.content)["id"]))
        result = _peer("content", "/internal/videos/analytics/summary", {"creator_id": creator_id})
        if (result is None or set(result) != {"total_videos", "videos_by_state"}
                or not _valid_count(result["total_videos"])
                or not isinstance(result["videos_by_state"], dict)
                or set(result["videos_by_state"]) != VIDEO_STATES
                or not all(_valid_count(value) for value in result["videos_by_state"].values())
                or result["total_videos"] != sum(result["videos_by_state"].values())):
            raise ValueError
        stats = _peer("engagement", "/internal/engagement/analytics/creator", {
            "creator_id": creator_id, "creator_user_id": user_id, "range": period})
        if not _valid_summary(stats, creator_id, user_id, period):
            raise ValueError
        top = []
        for row in stats["top_videos"]:
            detail = _peer("content", "/internal/videos/media/detail", {"creator_id": creator_id, "video_id": row["video_id"]})
            if detail is None:
                continue  # Deleted/non-owned rows cannot expose identifiers or titles.
            if not valid_video(detail, creator_id=creator_id, revision=True) or detail["id"] != row["video_id"]:
                raise ValueError
            top.append(row | {"title": detail["title"]})
        return JsonResponse(result | {key: value for key, value in stats.items()
                                      if key not in {"creator_id", "creator_user_id", "top_videos"}} | {"top_videos": top})
    except (ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return _error("Analytics temporarily unavailable", 503)


@never_cache
@require_GET
def creator_video_analytics(request, video_id):
    creator_id, error = _owned_creator(request)
    if error is not None:
        return error
    try:
        period = _range(request, {"7d", "since_published"})
    except ValueError:
        return _error("Invalid analytics request", 400)
    try:
        metadata = _peer("content", "/internal/videos/analytics/video",
                         {"creator_id": creator_id, "video_id": str(video_id)})
        if metadata is None:
            return _error("Video not found", 404)
        if set(metadata) != {"video_id", "state"} or metadata["video_id"] != str(video_id) or metadata["state"] not in VIDEO_STATES:
            raise ValueError
        published = None
        if period == "since_published":
            detail = _peer("content", "/internal/videos/media/detail", {"creator_id": creator_id, "video_id": str(video_id)})
            if detail is None:
                return _error("Video not found", 404)
            if not valid_video(detail, creator_id=creator_id, revision=True) or detail["id"] != str(video_id):
                raise ValueError
            published = detail["published_at"]
        counts = _peer("engagement", "/internal/engagement/analytics/video", {
            "video_id": str(video_id), "range": period, "published_at": published})
        if (counts is None or set(counts) != {"video_id", "current_likes", "qualified_viewers", "range",
                "qualified_plays", "watch_time_seconds", "likes", "shares", "average_watch_seconds"}
                or counts["video_id"] != str(video_id) or counts["range"] != period
                or not _valid_count(counts["current_likes"]) or not _valid_count(counts["qualified_viewers"])
                or not _valid_metrics(counts) or not _seconds(counts["average_watch_seconds"])
                or abs(counts["average_watch_seconds"] - (counts["watch_time_seconds"] / counts["qualified_plays"]
                                                        if counts["qualified_plays"] else 0)) > 0.001):
            raise ValueError
        return JsonResponse(metadata | {key: value for key, value in counts.items() if key != "video_id"})
    except (ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return _error("Analytics temporarily unavailable", 503)
