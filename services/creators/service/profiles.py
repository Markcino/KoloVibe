"""Only reviewed active creator profiles are discoverable."""

import json
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import CreatorProfile


def _public_profiles():
    return CreatorProfile.objects.filter(
        status=CreatorProfile.Status.ACTIVE,
        reviewed_at__isnull=False, restricted_at__isnull=True,
    )


def _profile_data(profile):
    return {"id": str(profile.id), "user_id": str(profile.user_id),
            "handle": profile.handle, "bio": profile.bio, "status": profile.status}


@require_POST
def internal_search(request):
    if len(request.body) > 1024:
        return JsonResponse({"detail": "Invalid search query"}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) - {"q", "cursor"}:
            raise ValueError
        query = data.get("q")
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100:
            raise ValueError
        query = query.strip()
        if any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in query):
            raise ValueError
        profiles = _public_profiles().filter(handle__icontains=query).order_by("id")
        if "cursor" in data:
            cursor = uuid.UUID(data["cursor"])
            if not profiles.filter(id=cursor).exists():
                raise ValueError
            profiles = profiles.filter(id__gt=cursor)
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"detail": "Invalid search query"}, status=400)
    page = list(profiles[:21])
    return JsonResponse({
        "items": [_profile_data(profile) for profile in page[:20]],
        "next_cursor": str(page[19].id) if len(page) > 20 else None,
    })


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
    profile = _public_profiles().filter(id=creator_id).first()
    if profile is None:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse(_profile_data(profile))
