"""Read-only public video endpoints from DOC-205's candidate interface."""

import json
import uuid

from django.http import JsonResponse
from django.db import models
from django.views.decorators.http import require_GET, require_POST

from .models import Video


def _public_videos():
    return Video.objects.filter(
        state=Video.State.PUBLISHED,
        visibility=Video.Visibility.PUBLIC,
        moderation_approved_at__isnull=False,
        provider_asset_id__isnull=False,
    ).exclude(provider_asset_id="")


def _item(video):
    data = {
        "id": str(video.id),
        "creator_id": str(video.creator_id),
        "title": video.title,
        "description": video.description,
        "state": video.state,
        "created_at": video.created_at.isoformat(),
    }
    if video.duration_seconds is not None:
        data["duration_seconds"] = video.duration_seconds
    return data


@require_GET
def list_videos(request):
    if (set(request.GET) - {"creator_id", "cursor", "q"}
            or any(len(request.GET.getlist(key)) != 1 for key in request.GET)):
        return JsonResponse({"detail": "Invalid query"}, status=400)
    return _list_videos(request.GET.get("creator_id"), request.GET.get("cursor"), request.GET.get("q"))


def _list_videos(creator, cursor, query):
    queryset = _public_videos().order_by("-created_at", "-id")
    if creator is not None:
        try:
            queryset = queryset.filter(creator_id=uuid.UUID(creator))
        except ValueError:
            return JsonResponse({"detail": "Invalid creator_id"}, status=400)
    if query is not None:
        if not 1 <= len(query.strip()) <= 100 or any(ord(char) < 32 for char in query):
            return JsonResponse({"detail": "Invalid search query"}, status=400)
        queryset = queryset.filter(
            models.Q(title__icontains=query.strip())
            | models.Q(description__icontains=query.strip())
        )
    if cursor is not None:
        try:
            cursor_id = uuid.UUID(cursor)
        except ValueError:
            return JsonResponse({"detail": "Invalid cursor"}, status=400)
        anchor = queryset.filter(pk=cursor_id).first()
        if anchor is None:
            return JsonResponse({"detail": "Invalid cursor"}, status=400)
        queryset = queryset.filter(
            models.Q(created_at__lt=anchor.created_at)
            | models.Q(created_at=anchor.created_at, id__lt=anchor.id)
        )
    page = list(queryset[:21])
    items = page[:20]
    return JsonResponse({
        "items": [_item(video) for video in items],
        "next_cursor": str(items[-1].id) if len(page) > 20 else None,
    })


@require_POST
def internal_list_videos(request):
    if len(request.body) > 1536:
        return JsonResponse({"detail": "Invalid request"}, status=400)
    try:
        filters = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    if not isinstance(filters, dict) or set(filters) - {"creator_id", "cursor", "q"}:
        return JsonResponse({"detail": "Invalid request"}, status=400)
    if any(value is not None and not isinstance(value, str) for value in filters.values()):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    return _list_videos(filters.get("creator_id"), filters.get("cursor"), filters.get("q"))


@require_GET
def video_detail(request, video_id):
    video = _public_videos().filter(pk=video_id).first()
    if video is None:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse(_item(video))


@require_POST
def internal_video_detail(request):
    if len(request.body) > 512:
        return JsonResponse({"detail": "Invalid request"}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"video_id"}:
            raise ValueError("Invalid request")
        video_id = uuid.UUID(data["video_id"])
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    video = _public_videos().filter(pk=video_id).first()
    if video is None:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse(_item(video))
