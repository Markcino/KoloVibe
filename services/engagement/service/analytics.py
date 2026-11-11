"""Current video engagement counts from Engagement-owned records."""

import json
from uuid import UUID

from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import VideoLike, WatchSession


@require_POST
def video_engagement(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 256:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"video_id"}:
            raise ValueError
        video_id = UUID(data["video_id"])
        return JsonResponse({
            "video_id": str(video_id),
            "current_likes": VideoLike.objects.filter(video_id=video_id).count(),
            "qualified_viewers": WatchSession.objects.filter(
                video_id=video_id, qualified_at__isnull=False,
            ).count(),
        })
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return JsonResponse({"detail": "Invalid analytics request"}, status=400)
    except DatabaseError:
        return JsonResponse({"detail": "Engagement temporarily unavailable"}, status=503)
