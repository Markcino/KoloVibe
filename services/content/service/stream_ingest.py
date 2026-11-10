"""Private video drafts, one-time upload intents and processing state."""

from base64 import b64decode
from binascii import Error as Base64Error
import json
import re
from uuid import UUID, uuid5

from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import stream_provider
from .models import Video


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


def _intent(creator_id, data):
    video_id, key = UUID(data["video_id"]), data["idempotency_key"]
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
        raise ValueError("Invalid idempotency key")
    video = Video.objects.filter(pk=video_id, creator_id=creator_id).first()
    if video is None:
        return _error("Video not found", 404)
    upload_id = uuid5(video_id, key)
    # Reserve before making the non-idempotent provider call. Ambiguous provider
    # outcomes stay reserved until reconciliation, including after worker failure.
    reserved = Video.objects.filter(
        pk=video_id, creator_id=creator_id, state=Video.State.DRAFT,
        visibility=Video.Visibility.PRIVATE, stream_upload_id__isnull=True, provider_asset_id__isnull=True,
    ).update(stream_upload_id=upload_id, state=Video.State.UPLOADING)
    if not reserved:
        return _error("An upload is already reserved or the video is not a private draft", 409)

    expires_at = timezone.now() + stream_provider.UPLOAD_LIFETIME
    uid, url = stream_provider.create_upload(video_id, expires_at)
    updated = Video.objects.filter(
        pk=video_id, state=Video.State.UPLOADING, visibility=Video.Visibility.PRIVATE,
        stream_upload_id=upload_id, provider_asset_id__isnull=True,
    ).update(provider_asset_id=uid)
    if not updated:
        return _error("Upload reservation requires reconciliation", 503)
    return JsonResponse({"video_id": str(video_id), "upload_id": str(upload_id),
                         "upload_url": url, "expires_at": expires_at.isoformat(),
                         "max_bytes": 200_000_000})


def _webhook(data):
    if not isinstance(data["body"], str):
        raise ValueError("Invalid webhook body")
    raw = b64decode(data["body"], validate=True)
    uid, ready = stream_provider.webhook_asset(raw, data["signature"])
    if not ready:
        return HttpResponse(status=204)
    videos = Video.objects.filter(
        provider_asset_id=uid, stream_upload_id__isnull=False, visibility=Video.Visibility.PRIVATE,
        state__in=(Video.State.UPLOADING, Video.State.PROCESSING),
    )
    video = videos.first()
    if video is None:
        return HttpResponse(status=204)
    if not stream_provider.asset_is_ready(uid, video.id):
        return _error("Stream processing confirmation pending", 503)
    videos.filter(pk=video.id).update(state=Video.State.REVIEW)
    return HttpResponse(status=204)


def _playback(data):
    video = Video.objects.filter(
        pk=UUID(data["video_id"]), state=Video.State.PUBLISHED, visibility=Video.Visibility.PUBLIC,
        moderation_approved_at__isnull=False, published_at__isnull=False, stream_upload_id__isnull=False,
    ).exclude(provider_asset_id__isnull=True).exclude(provider_asset_id="").first()
    if video is None:
        return _error("Video not found", 404)
    expires_at = timezone.now() + stream_provider.PLAYBACK_LIFETIME
    url = stream_provider.signed_playback(video.provider_asset_id, expires_at)
    return JsonResponse({"playback_url": url, "expires_at": expires_at.isoformat()})


@require_POST
def stream_ingest(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return _error("Forbidden", 403)
    try:
        if len(request.body) > 23000:
            raise ValueError("Request too large")
        data = json.loads(request.body)
        fields = {
            "draft": {"creator_id", "title", "description"},
            "intent": {"creator_id", "video_id", "idempotency_key"},
            "webhook": {"body", "signature"},
            "playback": {"video_id"},
        }
        if operation not in fields or not isinstance(data, dict) or set(data) != fields[operation]:
            raise ValueError("Invalid Stream request")
        if operation == "webhook":
            return _webhook(data)
        if operation == "playback":
            return _playback(data)
        creator_id = UUID(data["creator_id"])
        return _draft(creator_id, data) if operation == "draft" else _intent(creator_id, data)
    except stream_provider.InvalidStreamWebhook:
        return _error("Invalid Stream webhook", 403)
    except (stream_provider.StreamUnavailable, DatabaseError):
        return _error("Video service unavailable", 503)
    except (ValueError, TypeError, AttributeError, Base64Error):
        return _error("Invalid Stream request", 400)
