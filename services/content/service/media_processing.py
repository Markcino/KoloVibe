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
    upload = MediaUpload.objects.filter(video_id=video_id, video__state=Video.State.PROCESSING).first()
    if upload is None or not upload.source_etag:
        return None
    token, now = uuid4(), timezone.now()
    claimed = MediaUpload.objects.filter(
        pk=upload.pk, video__state=Video.State.PROCESSING,
    ).filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now)).update(
        lease_id=token, lease_until=now + LEASE,
    )
    if not claimed:
        if MediaUpload.objects.filter(pk=upload.pk, video__state=Video.State.PROCESSING).exists():
            raise LeaseBusy
        return None
    return upload, token


def _finish(upload, token, state, *, key=None, duration=None):
    with transaction.atomic():
        video = Video.objects.select_for_update().get(pk=upload.video_id)
        reservation = MediaUpload.objects.select_for_update().get(pk=upload.pk)
        if reservation.lease_id != token or video.state != Video.State.PROCESSING:
            return
        if state is not None:
            video.state = state
            video.provider_asset_id = key
            video.duration_seconds = duration
            video.save(update_fields=["state", "provider_asset_id", "duration_seconds"])
        reservation.lease_id = reservation.lease_until = None
        reservation.save(update_fields=["lease_id", "lease_until"])


def process(video_id):
    claimed = _claim(video_id)
    if claimed is None:
        return
    upload, token = claimed
    key = f"playback/{upload.id}/{token}.mp4"
    try:
        with TemporaryDirectory(prefix="kolovibe-media-") as directory:
            source, destination = Path(directory) / "source.mp4", Path(directory) / "playback.mp4"
            media_storage.download_upload(upload.source_key, upload.source_etag, upload.expected_bytes, source)
            duration = media_encoding.encode(source, destination)
            media_storage.put_playback(key, destination)
    except (media_encoding.InvalidMedia, media_storage.ObjectMissing, media_storage.ObjectChanged):
        _finish(upload, token, Video.State.FAILED)
    except (media_storage.StorageUnavailable, media_encoding.EncoderUnavailable, DatabaseError, OSError):
        _finish(upload, token, None)
        raise
    else:
        _finish(upload, token, Video.State.REVIEW, key=key, duration=duration)
