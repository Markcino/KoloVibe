"""Store a viewer's like without emitting engagement qualification or points."""

import json
from uuid import UUID

from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from .models import VideoLike


@require_POST
def update_like(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)

    try:
        if len(request.body) > 256:
            raise ValueError("Request too large")
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"video_id", "account_id", "liked"}:
            raise ValueError("Invalid like")
        if type(data["liked"]) is not bool:
            raise ValueError("Invalid like state")
        video_id = UUID(data["video_id"])
        account_id = UUID(data["account_id"])
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"detail": "Invalid like"}, status=400)

    try:
        if data["liked"]:
            VideoLike.objects.get_or_create(video_id=video_id, account_id=account_id)
            return JsonResponse({"video_id": str(video_id), "liked": True})
        VideoLike.objects.filter(video_id=video_id, account_id=account_id).delete()
    except DatabaseError:
        return JsonResponse({"detail": "Engagement service unavailable"}, status=503)
    return HttpResponse(status=204)
