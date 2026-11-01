"""Only reviewed active creator profiles are discoverable."""

import json
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import CreatorProfile


@require_POST
def internal_profile(request):
    if len(request.body) > 512:
        return JsonResponse({"detail": "Invalid request"}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"creator_id"}:
            raise ValueError("Invalid request")
        creator_id = uuid.UUID(data["creator_id"])
    except (ValueError, TypeError, KeyError, UnicodeError):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    profile = CreatorProfile.objects.filter(
        id=creator_id, status=CreatorProfile.Status.ACTIVE,
        reviewed_at__isnull=False, restricted_at__isnull=True,
    ).first()
    if profile is None:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse({"id": str(profile.id), "user_id": str(profile.user_id),
                         "handle": profile.handle, "bio": profile.bio, "status": profile.status})
