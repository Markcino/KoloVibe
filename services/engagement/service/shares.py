"""Idempotent, UTC-day share intent recording at the signed gateway boundary."""

from datetime import UTC
import json
from uuid import UUID

from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import VideoShare


@require_POST
def record_share(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 512:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"account_id", "video_id", "creator_id"}:
            raise ValueError
        values = {name: UUID(value) for name, value in data.items()}
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return JsonResponse({"detail": "Invalid share request"}, status=400)
    try:
        now = timezone.now().astimezone(UTC)
        with transaction.atomic():
            VideoShare.objects.get_or_create(
                account_id=values["account_id"], video_id=values["video_id"], day=now.date(),
                defaults={"creator_id": values["creator_id"], "created_at": now})
        return JsonResponse({"video_id": str(values["video_id"]), "recorded": True})
    except DatabaseError:
        return JsonResponse({"detail": "Engagement temporarily unavailable"}, status=503)
