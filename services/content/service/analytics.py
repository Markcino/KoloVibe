"""Creator-owned metadata analytics from Content records only."""

import json
from uuid import UUID

from django.db import DatabaseError
from django.db.models import Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Video


@require_POST
def content_analytics(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 512:
            raise ValueError
        data = json.loads(request.body)
        expected = {"creator_id"} if operation == "summary" else {"creator_id", "video_id"}
        if operation not in ("summary", "video") or not isinstance(data, dict) or set(data) != expected:
            raise ValueError
        creator_id = UUID(data["creator_id"])
        if operation == "video":
            video = Video.objects.filter(pk=UUID(data["video_id"]), creator_id=creator_id).first()
            if video is None:
                return JsonResponse({"detail": "Video not found"}, status=404)
            return JsonResponse({"video_id": str(video.id), "state": video.state})
        counts = {state: 0 for state in Video.State.values}
        for row in Video.objects.filter(creator_id=creator_id).values("state").annotate(count=Count("id")):
            counts[row["state"]] = row["count"]
        return JsonResponse({"total_videos": sum(counts.values()), "videos_by_state": counts})
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return JsonResponse({"detail": "Invalid analytics request"}, status=400)
    except DatabaseError:
        return JsonResponse({"detail": "Content temporarily unavailable"}, status=503)
