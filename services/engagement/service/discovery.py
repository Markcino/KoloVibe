"""Signed aggregate reads. Content remains authoritative for publication state."""

from datetime import timedelta
import json
from uuid import UUID

from django.core import signing
from django.db import DatabaseError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .models import CreatorFollow, QualifiedWatch, VideoLike

CURSOR_SALT = "kolovibe.engagement.trending.v1"


@require_POST
def discovery(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 4096:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        if operation == "like-counts":
            if set(data) != {"video_ids"} or not isinstance(data["video_ids"], list) or len(data["video_ids"]) > 50:
                raise ValueError
            ids = list(dict.fromkeys(UUID(value) for value in data["video_ids"]))
            counts = {str(value): 0 for value in ids}
            for row in VideoLike.objects.filter(video_id__in=ids).values("video_id").annotate(count=Count("id")):
                counts[str(row["video_id"])] = row["count"]
            return JsonResponse({"counts": counts})
        if operation == "follower-count":
            if set(data) != {"creator_id"}:
                raise ValueError
            creator_id = UUID(data["creator_id"])
            return JsonResponse({"creator_id": str(creator_id),
                                 "follower_count": CreatorFollow.objects.filter(creator_id=creator_id).count()})
        if operation != "trending" or set(data) != {"limit", "cursor"} or type(data["limit"]) is not int or not 1 <= data["limit"] <= 50:
            raise ValueError
        now, anchor = timezone.now(), None
        if data["cursor"] is not None:
            if not isinstance(data["cursor"], str) or len(data["cursor"]) > 2048:
                raise ValueError
            cursor = signing.loads(data["cursor"], salt=CURSOR_SALT, max_age=300)
            if not isinstance(cursor, dict) or set(cursor) != {"as_of", "plays", "video_id"}:
                raise ValueError
            as_of = parse_datetime(cursor["as_of"])
            if (as_of is None or as_of.tzinfo is None or as_of > now or as_of < now - timedelta(minutes=5)
                    or type(cursor["plays"]) is not int or cursor["plays"] < 1):
                raise ValueError
            anchor = cursor["plays"], UUID(cursor["video_id"])
        else:
            as_of = now
        ranked = QualifiedWatch.objects.filter(
            qualified_at__gte=as_of - timedelta(days=7), qualified_at__lte=as_of,
        ).values("video_id").annotate(qualified_plays=Count("id"))
        if anchor is not None:
            ranked = ranked.filter(Q(qualified_plays__lt=anchor[0])
                                   | Q(qualified_plays=anchor[0], video_id__gt=anchor[1]))
        rows = list(ranked.order_by("-qualified_plays", "video_id")[:data["limit"] + 1])
        items = [{"video_id": str(row["video_id"]), "qualified_plays": row["qualified_plays"]}
                 for row in rows[:data["limit"]]]
        next_cursor = signing.dumps({"as_of": as_of.isoformat(), "plays": items[-1]["qualified_plays"],
                                     "video_id": items[-1]["video_id"]}, salt=CURSOR_SALT) if len(rows) > data["limit"] else None
        return JsonResponse({"items": items, "next_cursor": next_cursor})
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, signing.BadSignature):
        return JsonResponse({"detail": "Invalid aggregate request"}, status=400)
    except DatabaseError:
        return JsonResponse({"detail": "Engagement temporarily unavailable"}, status=503)
