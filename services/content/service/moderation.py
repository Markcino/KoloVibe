"""Apply authenticated moderation decisions in the Content transaction."""

import json
from uuid import UUID

from django.db import DatabaseError, transaction
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ModerationReceipt, Video
from . import media_storage as storage


TRANSITIONS = {
    "publish": (Video.State.REVIEW, Video.State.PUBLISHED),
    "reject": (Video.State.REVIEW, Video.State.REJECTED),
    "remove": (Video.State.PUBLISHED, Video.State.REMOVED),
    "restore": (Video.State.REMOVED, Video.State.PUBLISHED),
}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _apply(video_id, action_id, action, revision):
    if not isinstance(action, str) or action not in TRANSITIONS or type(revision) is not int or revision < 0:
        raise ValueError("Invalid moderation transition")
    with transaction.atomic():
        video = Video.objects.select_for_update().filter(pk=video_id, deleted_at__isnull=True).first()
        if video is None:
            return _error("Video not found", 404)
        receipt = ModerationReceipt.objects.filter(pk=action_id).first()
        if receipt:
            if (receipt.video_id, receipt.action, receipt.previous_revision) != (video_id, action, revision):
                return _error("Moderation action conflict", 409)
            return JsonResponse({"applied": True})

        previous, new_state = TRANSITIONS[action]
        prior_visibility = Video.Visibility.PUBLIC if action == "remove" else Video.Visibility.PRIVATE
        if (video.moderation_revision != revision or video.state != previous
                or video.visibility != prior_visibility):
            return _error("Video state changed", 409)
        if new_state == Video.State.PUBLISHED:
            if not video.provider_asset_id:
                return _error("Processed video asset required", 409)
            now = timezone.now()
            video.moderation_approved_at = now
            # Reviewer approval does not make a new video public. Restoration
            # of a previously public removal is a separate moderated action.
            if action == "restore":
                video.published_at = video.published_at or now
        video.state = new_state
        video.visibility = Video.Visibility.PUBLIC if action == "restore" else Video.Visibility.PRIVATE
        video.moderation_revision += 1
        video.save(update_fields=[
            "state", "visibility", "moderation_revision", "moderation_approved_at", "published_at",
        ])
        ModerationReceipt.objects.create(action_id=action_id, video_id=video_id,
                                         action=action, previous_revision=revision)
    return JsonResponse({"applied": True})


@require_POST
def moderation_video(request, operation):
    if getattr(request, "service_caller", None) != "moderation":
        return _error("Forbidden", 403)
    try:
        if len(request.body) > 48000:
            raise ValueError("Request too large")
        data = json.loads(request.body)
        fields = {"inspect": {"video_id"}, "apply": {"video_id", "action_id", "action", "revision"},
                  "queue": {"cursor"}, "detail": {"video_id"}, "preview": {"video_id"}}
        if (operation not in fields or not isinstance(data, dict) or not fields[operation] <= set(data)
                or set(data) - fields[operation] - ({"scope_ids"} if operation == "queue" else set())):
            raise ValueError("Invalid moderation request")
        if operation == "queue":
            videos = Video.objects.filter(state=Video.State.REVIEW, visibility=Video.Visibility.PRIVATE,
                                           deleted_at__isnull=True).order_by("id")
            if "scope_ids" in data:
                ids = data["scope_ids"]
                if not isinstance(ids, list) or len(ids) > 1000 or any(not isinstance(item, str) for item in ids):
                    raise ValueError("Invalid assignment scope")
                videos = videos.filter(id__in=[UUID(item) for item in ids])
            if data["cursor"] is not None:
                videos = videos.filter(id__gt=UUID(data["cursor"]))
            page = list(videos[:21])
            items = [{"id": str(video.id), "title": video.title} for video in page[:20]]
            return JsonResponse({"items": items, "next_cursor": items[-1]["id"] if len(page) > 20 else None})
        video_id = UUID(data["video_id"])
        if operation == "apply":
            return _apply(video_id, UUID(data["action_id"]), data["action"], data["revision"])
        video = Video.objects.filter(pk=video_id, deleted_at__isnull=True).first()
        if video is None:
            return _error("Video not found", 404)
        if operation == "detail":
            return JsonResponse({"id": str(video.id), "title": video.title, "description": video.description,
                "state": video.state, "duration_seconds": video.duration_seconds,
                "rights_status": "not_recorded", "preview_available": bool(video.provider_asset_id
                    and video.provider_asset_id.startswith("playback/"))})
        if operation == "preview":
            if not video.provider_asset_id or not video.provider_asset_id.startswith("playback/"):
                return _error("Preview unavailable", 404)
            response = HttpResponse(storage.read_preview(video.provider_asset_id), content_type="video/mp4")
            response["Cache-Control"] = "private, no-store"
            return response
        return JsonResponse({"creator_id": str(video.creator_id), "state": video.state,
                             "visibility": video.visibility, "revision": video.moderation_revision})
    except (ValueError, TypeError, AttributeError):
        return _error("Invalid moderation request", 400)
    except (storage.StorageUnavailable, storage.ObjectMissing):
        return _error("Preview unavailable", 503)
    except DatabaseError:
        return _error("Video service unavailable", 503)
