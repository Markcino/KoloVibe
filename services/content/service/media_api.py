"""Private drafts, conditional R2 uploads and approved VOD playback."""

from datetime import timedelta
import json
import logging
import re
from uuid import UUID, uuid5

from django.db import DatabaseError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from kombu.exceptions import KombuError

from . import media_storage as storage
from .models import MediaUpload, Video, OriginalityAttestation
from .copyright import ATTESTATION_VERSION, audit
from .video_metadata import FIELDS, item, metadata

logger = logging.getLogger(__name__)


UPLOAD_LIFETIME = timedelta(minutes=10)
PLAYBACK_SECONDS = 300


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _draft(creator_id, data):
    values = metadata({key: value for key, value in data.items() if key in FIELDS}, creating=True)
    video = Video.objects.create(creator_id=creator_id, **values)
    return JsonResponse(item(video), status=201)


def _intent(video_id, creator_id, data):
    size, key = data["size_bytes"], data["idempotency_key"]
    actor = UUID(data["account_id"])
    attestation, policy = data["originality_attestation"], data["review_policy"]
    if (attestation != {"version": ATTESTATION_VERSION, "accepted": True}
            or not isinstance(attestation, dict) or attestation.get("accepted") is not True
            or not isinstance(policy, dict) or set(policy) != {"trusted", "sample_percent", "policy_version"}
            or type(policy["trusted"]) is not bool or type(policy["sample_percent"]) is not int
            or not 0 <= policy["sample_percent"] <= 100
            or (policy["trusted"] and (not isinstance(policy["policy_version"], str) or not 1 <= len(policy["policy_version"]) <= 32))
            or (not policy["trusted"] and (policy["sample_percent"] != 100 or policy["policy_version"] is not None))):
        raise ValueError("Originality attestation and verified policy required")
    if (type(size) is not int or not 0 < size <= storage.MAX_BYTES
            or not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key)):
        raise ValueError("Invalid upload intent")
    upload_id = uuid5(video_id, key)
    with transaction.atomic():
        video = Video.objects.select_for_update().filter(pk=video_id, creator_id=creator_id, deleted_at__isnull=True).first()
        if video is None:
            return _error("Video not found", 404)
        if video.state not in (Video.State.DRAFT, Video.State.UPLOADING, Video.State.FAILED) or video.visibility != Video.Visibility.PRIVATE:
            return _error("Video is not eligible for upload", 409)
        upload = MediaUpload.objects.select_for_update().filter(video_id=video_id).first()
        if upload is not None and upload.id == upload_id:
            if upload.expected_bytes != size:
                return _error("A different upload is reserved", 409)
            if upload.expires_at <= timezone.now() or video.state == Video.State.FAILED:
                return _error("Use a new Idempotency-Key to retry the upload", 409)
        elif upload is not None:
            # Old presigned PUTs may live until expiry but no longer identify the
            # current reservation. Keep stored objects private; never purge here.
            MediaUpload.objects.filter(pk=upload.id).update(
                id=upload_id, expected_bytes=size, expires_at=timezone.now() + UPLOAD_LIFETIME,
                source_etag="", lease_id=None, lease_until=None)
            upload = MediaUpload.objects.get(pk=upload_id)
        else:
            upload = MediaUpload.objects.create(
                id=upload_id, video=video, expected_bytes=size, expires_at=timezone.now() + UPLOAD_LIFETIME,
            )
        video.state = Video.State.UPLOADING
        evidence, created = OriginalityAttestation.objects.get_or_create(upload_id=upload_id, defaults={
            "video": video, "account_id": actor, "version": ATTESTATION_VERSION, "review_policy": policy})
        if (evidence.video_id, evidence.account_id, evidence.version) != (video.id, actor, ATTESTATION_VERSION):
            return _error("Attestation conflicts with reservation", 409)
        if created:
            audit(video, "originality_attested", "Creator accepted originality and permission attestation",
                  actor=actor, payload={"version": ATTESTATION_VERSION, "upload_id": str(upload_id)})
        video.rights_status = Video.RightsStatus.ATTESTED
        video.failure_reason = None
        video.provider_asset_id = video.poster_asset_id = None
        video.duration_ms = video.duration_seconds = None
        video.save(update_fields=["state", "failure_reason", "provider_asset_id", "poster_asset_id",
                                  "duration_ms", "duration_seconds", "rights_status"])
    seconds = int((upload.expires_at - timezone.now()).total_seconds())
    if seconds <= 0:
        return _error("Upload reservation expired", 409)
    return JsonResponse({"video_id": str(video_id), "upload_id": str(upload_id),
                         "upload_url": storage.sign_upload(upload.source_key, size, seconds),
                         "upload_headers": storage.upload_headers(size),
                         "expires_at": upload.expires_at.isoformat(), "max_bytes": storage.MAX_BYTES})


def _status(video):
    return {"video_id": str(video.id), "state": video.state, "failure_reason": video.failure_reason,
            "retryable": video.state in {"draft", "uploading", "failed"}
            or video.state == "processing" and video.failure_reason is not None}


def _owned_item(video):
    return item(video)


def _owned_detail(video):
    return _owned_item(video) | {"revision": video.moderation_revision}


def _library(creator_id, cursor, state="all", query=None):
    allowed = {"all", "draft", "in_progress", "review", "published", "rejected", "removed", "failed"}
    if state not in allowed:
        raise ValueError("Invalid library state")
    videos = Video.objects.filter(creator_id=creator_id, deleted_at__isnull=True).order_by("-created_at", "-id")
    if state != "all":
        videos = videos.filter(state__in=["uploading", "processing"] if state == "in_progress" else [state])
    if query is not None:
        # The same rule as public search, applied only to the creator's own non-deleted videos.
        if (not isinstance(query, str) or not 1 <= len(query.strip()) <= 100
                or any(ord(char) < 32 for char in query)):
            raise ValueError("Invalid library search")
        videos = videos.filter(Q(title__icontains=query.strip()) | Q(description__icontains=query.strip()))
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
            pk=video_id, creator_id=creator_id, deleted_at__isnull=True).first()
        if video is None:
            return _error("Video not found", 404)
        if operation == "delete":
            now = timezone.now()
            video.deleted_at = now
            video.visibility = Video.Visibility.PRIVATE
            video.moderation_revision += 1
            video.save(update_fields=["deleted_at", "visibility", "moderation_revision"])
            MediaUpload.objects.filter(video=video).update(expires_at=now, lease_id=None, lease_until=None)
            return JsonResponse({"video_id": str(video_id), "deleted": True})
        if operation in {"publish", "unpublish"}:
            if (video.state != Video.State.PUBLISHED or not video.moderation_approved_at
                    or not video.provider_asset_id
                    or operation == "publish" and video.visibility != Video.Visibility.PRIVATE):
                return JsonResponse({"detail": "Moderation approval required", "code": "review_required"}, status=409)
            desired = Video.Visibility.PUBLIC if operation == "publish" else Video.Visibility.PRIVATE
            if video.visibility != desired:
                video.visibility = desired
                video.moderation_revision += 1
                if desired == Video.Visibility.PUBLIC and video.published_at is None:
                    video.published_at = timezone.now()
                video.save(update_fields=["visibility", "moderation_revision", "published_at"])
            return JsonResponse(_owned_item(video))
        if video.state not in {Video.State.DRAFT, Video.State.FAILED, Video.State.REJECTED, Video.State.PUBLISHED}:
            return _error("Video cannot be edited in its current state", 409)
        duration = video.duration_ms
        if duration is None and video.duration_seconds is not None:
            duration = video.duration_seconds * 1000
        values = metadata({key: value for key, value in data.items() if key in FIELDS}, duration_ms=duration)
        changed = {name: value for name, value in values.items() if getattr(video, name) != value}
        if "cover_time_ms" in changed:
            # A cover edit clears the stale frame. For a processed video the media worker renders the new one
            # from the private rendition after commit (D-P2-01); no network or FFmpeg work runs under this lock.
            video.poster_asset_id = None
            changed["poster_asset_id"] = None
            if video.provider_asset_id:
                transaction.on_commit(lambda video_id=video.id: _queue_cover(video_id))
        for name, value in changed.items():
            setattr(video, name, value)
        if changed:
            # M-054 says "Save changes" and does not request another review.
            video.moderation_revision += 1
            video.save(update_fields=[*changed, "moderation_revision"])
        return JsonResponse(_owned_item(video))


def _enqueue(video_id):
    from .media_tasks import process_video

    # Celery may fall back to amq.default when no explicit exchange is given.
    # The scoped Content RabbitMQ account can publish only to this exchange.
    process_video.apply_async(
        args=[str(video_id)],
        queue="kolovibe.content.media",
        exchange="kolovibe.content.media",
        routing_key="kolovibe.content.media",
        retry=False,
    )


def _enqueue_cover(video_id):
    from .media_tasks import render_cover

    render_cover.apply_async(
        args=[str(video_id)],
        queue="kolovibe.content.media",
        exchange="kolovibe.content.media",
        routing_key="kolovibe.content.media",
        retry=False,
    )


def _queue_cover(video_id):
    """Best effort after commit: a broker outage never fails the saved edit; `requeue_stalled_media` recovers it."""
    try:
        _enqueue_cover(video_id)
    except (KombuError, OSError, RuntimeError, ImportError):
        logger.warning("Cover render could not be queued; recovery will retry")


def _complete(video_id, creator_id):
    video = Video.objects.filter(pk=video_id, creator_id=creator_id, deleted_at__isnull=True).first()
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
            video = Video.objects.select_for_update().filter(pk=video_id, deleted_at__isnull=True).first()
            if video is None:
                return _error("Video not found", 404)
            current_upload = MediaUpload.objects.select_for_update().filter(video=video).first()
            if (current_upload is None or current_upload.id != upload.id
                    or current_upload.expected_bytes != upload.expected_bytes):
                return _error("Upload reservation changed", 409)
            if video.state == Video.State.UPLOADING:
                current_upload.source_etag = etag
                current_upload.save(update_fields=["source_etag"])
                video.state = Video.State.PROCESSING
                video.failure_reason = None
                video.save(update_fields=["state", "failure_reason"])
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
        deleted_at__isnull=True,
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
            "draft": {"creator_id", "title", "category"},
            "library": {"creator_id", "cursor"},
            "detail": {"creator_id", "video_id"},
            "edit": {"creator_id", "video_id"},
            "delete": {"creator_id", "video_id"},
            "publish": {"creator_id", "video_id"}, "unpublish": {"creator_id", "video_id"},
            "intent": {"creator_id", "video_id", "idempotency_key", "size_bytes", "account_id", "originality_attestation", "review_policy"},
            "complete": {"creator_id", "video_id"}, "status": {"creator_id", "video_id"},
            "playback": {"video_id"}, "watch": {"video_id"}, "watch-check": {"video_id"},
        }
        optional = FIELDS if operation in {"draft", "edit"} else {"state", "q"} if operation == "library" else set()
        if (operation not in fields or not isinstance(data, dict)
                or not fields[operation] <= set(data) or set(data) - fields[operation] - optional):
            raise ValueError("Invalid media request")
        if operation in ("playback", "watch", "watch-check"):
            return _playback(UUID(data["video_id"]), operation)
        creator_id = UUID(data["creator_id"])
        if operation == "draft":
            return _draft(creator_id, data)
        if operation == "library":
            return _library(creator_id, data["cursor"], data.get("state", "all"), data.get("q"))
        video_id = UUID(data["video_id"])
        if operation in ("edit", "delete", "publish", "unpublish"):
            return _manage(video_id, creator_id, data, operation)
        if operation == "intent":
            return _intent(video_id, creator_id, data)
        if operation == "complete":
            return _complete(video_id, creator_id)
        video = Video.objects.filter(pk=video_id, creator_id=creator_id, deleted_at__isnull=True).first()
        if operation == "detail":
            return JsonResponse(_owned_detail(video)) if video else _error("Video not found", 404)
        return JsonResponse(_status(video)) if video else _error("Video not found", 404)
    except (storage.StorageUnavailable, storage.ObjectChanged, DatabaseError, KombuError, RuntimeError, OSError):
        return _error("Media temporarily unavailable", 503)
    except (ValueError, TypeError, AttributeError):
        return _error("Invalid media request", 400)
