"""Lease-backed worker for private R2 source media."""

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from . import media_encoding, media_storage
from .models import MediaUpload, Video


LEASE = timedelta(minutes=10)


class LeaseBusy(Exception):
    pass


def _claim(video_id):
    upload = MediaUpload.objects.select_related("video").filter(
        video_id=video_id, video__state=Video.State.PROCESSING, video__deleted_at__isnull=True).first()
    if upload is None or not upload.source_etag:
        return None
    token, now = uuid4(), timezone.now()
    claimed = MediaUpload.objects.filter(
        pk=upload.pk, video__state=Video.State.PROCESSING, video__deleted_at__isnull=True,
    ).filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now)).update(
        lease_id=token, lease_until=now + LEASE,
    )
    if not claimed:
        if MediaUpload.objects.filter(pk=upload.pk, video__state=Video.State.PROCESSING,
                                      video__deleted_at__isnull=True).exists():
            raise LeaseBusy
        return None
    return upload, token


def _finish(upload, token, state, *, key=None, duration=None, poster=None, failure=None):
    with transaction.atomic():
        video = Video.objects.select_for_update().filter(pk=upload.video_id, deleted_at__isnull=True).first()
        reservation = MediaUpload.objects.select_for_update().filter(pk=upload.pk).first()
        if (video is None or reservation is None or reservation.lease_id != token
                or video.state != Video.State.PROCESSING):
            return
        if state is not None:
            video.state = state
            video.provider_asset_id = key
            video.duration_ms = duration
            video.duration_seconds = (duration + 999) // 1000 if duration is not None else None
            video.poster_asset_id = poster
            video.save(update_fields=["state", "provider_asset_id", "duration_seconds", "duration_ms", "poster_asset_id"])
        video.failure_reason = failure
        video.save(update_fields=["failure_reason"])
        reservation.lease_id = reservation.lease_until = None
        reservation.save(update_fields=["lease_id", "lease_until"])


def process(video_id):
    claimed = _claim(video_id)
    if claimed is None:
        return
    upload, token = claimed
    key = f"playback/{upload.id}/{token}.mp4"
    poster_key = f"playback/{upload.id}/{token}.jpg"
    try:
        with TemporaryDirectory(prefix="kolovibe-media-") as directory:
            source, destination = Path(directory) / "source.mp4", Path(directory) / "playback.mp4"
            poster = Path(directory) / "poster.jpg"
            media_storage.download_upload(upload.source_key, upload.source_etag, upload.expected_bytes, source)
            duration = media_encoding.encode(source, destination)
            cover = upload.video.cover_time_ms
            if cover is not None and cover > duration:
                _finish(upload, token, Video.State.FAILED, failure="cover_out_of_range")
                return
            if cover is None:
                cover = 1000 if duration > 1000 else 0
            try:
                media_encoding.render_poster(destination, poster, cover, duration)
            except media_encoding.InvalidMedia:
                _finish(upload, token, Video.State.FAILED, failure="poster_failed")
                return
            media_storage.put_playback(key, destination)
            media_storage.put_poster(poster_key, poster)
    except media_encoding.InvalidMedia:
        _finish(upload, token, Video.State.FAILED, failure="invalid_media")
    except media_storage.ObjectMissing:
        _finish(upload, token, Video.State.FAILED, failure="upload_missing")
    except media_storage.ObjectChanged:
        _finish(upload, token, Video.State.FAILED, failure="upload_changed")
    except (media_storage.StorageUnavailable, media_encoding.EncoderUnavailable, DatabaseError, OSError):
        _finish(upload, token, None, failure="processing_unavailable")
        raise
    else:
        _finish(upload, token, Video.State.REVIEW, key=key, duration=duration, poster=poster_key)
