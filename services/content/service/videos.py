"""Read-only public video endpoints from DOC-205's candidate interface."""

import uuid

from django.http import JsonResponse
from django.db import models
from django.views.decorators.http import require_GET

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
    queryset = _public_videos().order_by("-created_at", "-id")
    creator = request.GET.get("creator_id")
    if creator is not None:
        try:
            queryset = queryset.filter(creator_id=uuid.UUID(creator))
        except ValueError:
            return JsonResponse({"detail": "Invalid creator_id"}, status=400)
    cursor = request.GET.get("cursor")
    if cursor is not None:
        try:
            cursor_id = uuid.UUID(cursor)
        except ValueError:
            return JsonResponse({"detail": "Invalid cursor"}, status=400)
        anchor = _public_videos().filter(pk=cursor_id).first()
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


@require_GET
def video_detail(request, video_id):
    video = _public_videos().filter(pk=video_id).first()
    if video is None:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse(_item(video))
