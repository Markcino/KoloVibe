"""Private drafts, conditional R2 uploads and approved VOD playback."""

from datetime import timedelta
import json
import re
from uuid import UUID, uuid5

from django.db import DatabaseError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from kombu.exceptions import KombuError

from . import media_storage as storage
from .models import MediaUpload, Video


UPLOAD_LIFETIME = timedelta(minutes=10)
PLAYBACK_SECONDS = 300


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _draft(creator_id, data):
    title, description = data["title"], data["description"]
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
        raise ValueError("Invalid title")
    if not isinstance(description, str) or len(description) > 2000:
        raise ValueError("Invalid description")
    video = Video.objects.create(creator_id=creator_id, title=title.strip(), description=description)
    return JsonResponse({
        "id": str(video.id), "creator_id": str(video.creator_id), "title": video.title,
        "description": video.description, "state": video.state,
        "created_at": video.created_at.isoformat(),
    }, status=201)


def _intent(video_id, creator_id, data):
    size, key = data["size_bytes"], data["idempotency_key"]
    if (type(size) is not int or not 0 < size <= storage.MAX_BYTES
            or not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key)):
        raise ValueError("Invalid upload intent")
    upload_id = uuid5(video_id, key)
    with transaction.atomic():
        video = Video.objects.select_for_update().filter(pk=video_id, creator_id=creator_id).first()
        if video is None:
            return _error("Video not found", 404)
        if video.state not in (Video.State.DRAFT, Video.State.UPLOADING) or video.visibility != Video.Visibility.PRIVATE:
            return _error("Video is not eligible for upload", 409)
        upload = MediaUpload.objects.filter(video_id=video_id).first()
        if upload is None and video.state == Video.State.DRAFT:
            upload = MediaUpload.objects.create(
                id=upload_id, video=video, expected_bytes=size, expires_at=timezone.now() + UPLOAD_LIFETIME,
            )
            video.state = Video.State.UPLOADING
            video.save(update_fields=["state"])
        if upload is None or upload.id != upload_id or upload.expected_bytes != size:
            return _error("A different upload is reserved", 409)
    seconds = int((upload.expires_at - timezone.now()).total_seconds())
    if seconds <= 0:
        return _error("Upload reservation expired", 409)
    return JsonResponse({"video_id": str(video_id), "upload_id": str(upload_id),
                         "upload_url": storage.sign_upload(upload.source_key, size, seconds),
                         "upload_headers": storage.upload_headers(size),
                         "expires_at": upload.expires_at.isoformat(), "max_bytes": storage.MAX_BYTES})


def _status(video):
    return {"video_id": str(video.id), "state": video.state}


def _owned_item(video):
    return {"id": str(video.id), "creator_id": str(video.creator_id),
            "title": video.title, "description": video.description,
            "state": video.state, "created_at": video.created_at.isoformat()}


def _library(creator_id, cursor):
    videos = Video.objects.filter(creator_id=creator_id).order_by("-created_at", "-id")
    if cursor is not None:
        anchor = videos.filter(pk=UUID(cursor)).first()
        if anchor is None:
            return _error("Invalid cursor", 400)
        videos = videos.filter(Q(created_at__lt=anchor.created_at) |
                               Q(created_at=anchor.created_at, id__lt=anchor.id))
    page = list(videos[:21])
    return JsonResponse({"items": [_owned_item(item) for item in page[:20]],
                         "next_cursor": str(page[19].id) if len(page) > 20 else None})


def _manage(video_id, creator_id, data, operation):
    with transaction.atomic():
        video = Video.objects.select_for_update().filter(
            pk=video_id, creator_id=creator_id).first()
        if video is None:
            return _error("Video not found", 404)
        if (video.state != Video.State.DRAFT or video.visibility != Video.Visibility.PRIVATE
                or video.provider_asset_id or MediaUpload.objects.filter(video=video).exists()):
            return _error("Only a private draft without media can be changed", 409)
        if operation == "delete":
            video.delete()
            return JsonResponse({"video_id": str(video_id), "deleted": True})
        title, description = data["title"], data["description"]
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
            raise ValueError("Invalid title")
        if not isinstance(description, str) or len(description) > 2000:
            raise ValueError("Invalid description")
        video.title = title.strip()
        video.description = description
        video.save(update_fields=["title", "description"])
        return JsonResponse(_owned_item(video))


def _enqueue(video_id):
    from .media_tasks import process_video

    process_video.apply_async(args=[str(video_id)], retry=False)


def _complete(video_id, creator_id):
    video = Video.objects.filter(pk=video_id, creator_id=creator_id).first()
    if video is None:
        return _error("Video not found", 404)
    if video.state == Video.State.UPLOADING:
        upload = MediaUpload.objects.filter(video_id=video_id).first()
        if upload is None:
            return _error("Upload reservation not found", 409)
        try:
            length, content_type, etag = storage.inspect_upload(upload.source_key)
        except storage.ObjectMissing:
            return _error("Upload is not available in R2", 409)
        if (length != upload.expected_bytes or content_type != storage.CONTENT_TYPE
                or not isinstance(etag, str) or not re.fullmatch(r'"[A-Za-z0-9-]{1,124}"', etag)):
            return _error("Stored object does not match the upload reservation", 409)
        with transaction.atomic():
            video = Video.objects.select_for_update().get(pk=video_id)
            if video.state == Video.State.UPLOADING:
                upload.source_etag = etag
                upload.save(update_fields=["source_etag"])
                video.state = Video.State.PROCESSING
                video.save(update_fields=["state"])
    if video.state == Video.State.DRAFT:
        return _error("Upload reservation not found", 409)
    if video.state == Video.State.PROCESSING:
        _enqueue(video_id)
        return JsonResponse(_status(video), status=202)
    return JsonResponse(_status(video))


def _playback(video_id, operation):
    video = Video.objects.filter(
        pk=video_id, state=Video.State.PUBLISHED, visibility=Video.Visibility.PUBLIC,
        moderation_approved_at__isnull=False, published_at__isnull=False, media_upload__isnull=False,
    ).first()
    if video is None or not video.provider_asset_id or not video.provider_asset_id.startswith("playback/"):
        return _error("Video not found", 404)
    result = {}
    if operation != "playback":
        if not video.duration_ms:
            return _error("Tracked playback unavailable", 409)
        result.update(creator_id=str(video.creator_id), duration_ms=video.duration_ms,
                      revision=video.moderation_revision)
    if operation != "watch-check":
        expires_at = timezone.now() + timedelta(seconds=PLAYBACK_SECONDS)
        result.update(playback_url=storage.sign_playback(video.provider_asset_id, PLAYBACK_SECONDS),
                      expires_at=expires_at.isoformat())
    return JsonResponse(result)


@require_POST
def media_api(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return _error("Forbidden", 403)
    try:
        if len(request.body) > 32768:
            raise ValueError("Request too large")
        data = json.loads(request.body)
        fields = {
            "draft": {"creator_id", "title", "description"},
            "library": {"creator_id", "cursor"},
            "edit": {"creator_id", "video_id", "title", "description"},
            "delete": {"creator_id", "video_id"},
            "intent": {"creator_id", "video_id", "idempotency_key", "size_bytes"},
            "complete": {"creator_id", "video_id"}, "status": {"creator_id", "video_id"},
            "playback": {"video_id"}, "watch": {"video_id"}, "watch-check": {"video_id"},
        }
        if operation not in fields or not isinstance(data, dict) or set(data) != fields[operation]:
            raise ValueError("Invalid media request")
        if operation in ("playback", "watch", "watch-check"):
            return _playback(UUID(data["video_id"]), operation)
        creator_id = UUID(data["creator_id"])
        if operation == "draft":
            return _draft(creator_id, data)
        if operation == "library":
            return _library(creator_id, data["cursor"])
        video_id = UUID(data["video_id"])
        if operation in ("edit", "delete"):
            return _manage(video_id, creator_id, data, operation)
        if operation == "intent":
            return _intent(video_id, creator_id, data)
        if operation == "complete":
            return _complete(video_id, creator_id)
        video = Video.objects.filter(pk=video_id, creator_id=creator_id).first()
        return JsonResponse(_status(video)) if video else _error("Video not found", 404)
    except (storage.StorageUnavailable, storage.ObjectChanged, DatabaseError, KombuError, RuntimeError, OSError):
        return _error("Media temporarily unavailable", 503)
    except (ValueError, TypeError, AttributeError):
        return _error("Invalid media request", 400)
