"""Account-owned creator follows, called only by the gateway."""

import json
from uuid import UUID

from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from .models import CreatorFollow


@require_POST
def followed_creators(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if len(request.body) > 1024:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"account_id", "creator_ids"}:
            raise ValueError
        account_id = UUID(data["account_id"])
        ids = data["creator_ids"]
        if not isinstance(ids, list) or len(ids) > 20 or len(set(ids)) != len(ids):
            raise ValueError
        creator_ids = [UUID(value) for value in ids]
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"detail": "Invalid follow request"}, status=400)
    try:
        followed = CreatorFollow.objects.filter(
            account_id=account_id, creator_id__in=creator_ids,
        ).values_list("creator_id", flat=True)
        return JsonResponse({"creator_ids": sorted(str(value) for value in followed)})
    except DatabaseError:
        return JsonResponse({"detail": "Engagement service unavailable"}, status=503)


@require_POST
def follow_api(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if len(request.body) > 256:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"account_id", "creator_id", "operation"}:
            raise ValueError
        account_id = UUID(data["account_id"])
        creator_id = UUID(data["creator_id"])
        operation = data["operation"]
        if operation not in ("follow", "unfollow", "status"):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"detail": "Invalid follow request"}, status=400)
    try:
        matches = CreatorFollow.objects.filter(account_id=account_id, creator_id=creator_id)
        if operation == "follow":
            CreatorFollow.objects.get_or_create(account_id=account_id, creator_id=creator_id)
        elif operation == "unfollow":
            matches.delete()
            return HttpResponse(status=204)
        return JsonResponse({"creator_id": str(creator_id), "following": matches.exists()})
    except DatabaseError:
        return JsonResponse({"detail": "Engagement service unavailable"}, status=503)
