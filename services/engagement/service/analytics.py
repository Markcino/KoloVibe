"""Current video engagement counts from Engagement-owned records."""

from datetime import UTC, datetime, time, timedelta
import json
from uuid import UUID

from django.db import DatabaseError
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import CreatorFollow, QualifiedWatch, VideoLike, VideoShare, WatchSession


def _start(now, days):
    return datetime.combine(now.date() - timedelta(days=days - 1), time.min, UTC)


def _between(query, field, start, now):
    query = query.filter(**{field + "__lte": now})
    return query.filter(**{field + "__gte": start}) if start is not None else query


def _metrics(plays, likes, shares):
    count = plays.count()
    seconds = round((plays.aggregate(total=Sum("watched_ms"))["total"] or 0) / 1000, 3)
    return {"qualified_plays": count, "watch_time_seconds": seconds,
            "likes": likes.count(), "shares": shares.count()}


@require_POST
def creator_engagement(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 512:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"creator_id", "creator_user_id", "range"} or data["range"] not in {"7d", "28d"}:
            raise ValueError
        creator_id, owner = UUID(data["creator_id"]), UUID(data["creator_user_id"])
        now = timezone.now().astimezone(UTC)
        days = 7 if data["range"] == "7d" else 28
        start = _start(now, days)
        plays = _between(QualifiedWatch.objects.filter(creator_user_id=owner), "qualified_at", start, now)
        likes = _between(VideoLike.objects.filter(creator_id=creator_id), "created_at", start, now)
        shares = _between(VideoShare.objects.filter(creator_id=creator_id), "created_at", start, now)
        result = _metrics(plays, likes, shares)
        result["new_followers"] = _between(CreatorFollow.objects.filter(creator_id=creator_id), "created_at", start, now).count()
        result.update(creator_id=str(creator_id), creator_user_id=str(owner), range=data["range"])
        play_days = {row["date"].isoformat(): row["count"] for row in plays.annotate(
            date=TruncDate("qualified_at", tzinfo=UTC)).values("date").annotate(count=Count("id"))}
        like_days = {row["date"].isoformat(): row["count"] for row in likes.annotate(
            date=TruncDate("created_at", tzinfo=UTC)).values("date").annotate(count=Count("id"))}
        result["daily"] = [{"date": (start.date() + timedelta(days=index)).isoformat(),
                            "qualified_plays": play_days.get((start.date() + timedelta(days=index)).isoformat(), 0),
                            "likes": like_days.get((start.date() + timedelta(days=index)).isoformat(), 0)}
                           for index in range(days)] if play_days or like_days else []
        result["top_videos"] = [{"video_id": str(row["video_id"]), "qualified_plays": row["qualified_plays"]}
                                for row in plays.values("video_id").annotate(qualified_plays=Count("id")).order_by(
                                    "-qualified_plays", "video_id")[:5]]
        return JsonResponse(result)
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        return JsonResponse({"detail": "Invalid analytics request"}, status=400)
    except DatabaseError:
        return JsonResponse({"detail": "Engagement temporarily unavailable"}, status=503)


@require_POST
def video_engagement(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 512:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) not in ({"video_id"}, {"video_id", "range", "published_at"}):
            raise ValueError
        video_id = UUID(data["video_id"])
        result = {
            "video_id": str(video_id),
            "current_likes": VideoLike.objects.filter(video_id=video_id).count(),
            "qualified_viewers": WatchSession.objects.filter(
                video_id=video_id, qualified_at__isnull=False,
            ).count(),
        }
        if "range" in data:
            if data["range"] not in {"7d", "since_published"}:
                raise ValueError
            now = timezone.now().astimezone(UTC)
            published = data["published_at"]
            if published is not None:
                if not isinstance(published, str) or len(published) > 64:
                    raise ValueError
                published = parse_datetime(published)
                if published is None or published.tzinfo is None or published > now:
                    raise ValueError
            start = _start(now, 7) if data["range"] == "7d" else published
            plays = _between(QualifiedWatch.objects.filter(video_id=video_id), "qualified_at", start, now)
            likes = _between(VideoLike.objects.filter(video_id=video_id), "created_at", start, now)
            shares = _between(VideoShare.objects.filter(video_id=video_id), "created_at", start, now)
            result.update(_metrics(plays, likes, shares), range=data["range"])
            result["average_watch_seconds"] = round(result["watch_time_seconds"] / result["qualified_plays"], 3) if result["qualified_plays"] else 0.0
        return JsonResponse(result)
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return JsonResponse({"detail": "Invalid analytics request"}, status=400)
    except DatabaseError:
        return JsonResponse({"detail": "Engagement temporarily unavailable"}, status=503)
