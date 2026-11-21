"""Lease-backed worker for private R2 source media."""

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from . import media_encoding, media_storage, screening, copyright
from .models import Fingerprint, MediaUpload, ScreeningRecord, Video


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


def _record(video, outcome):
    """Append the audit trail for every automated finding and the final decision, and keep prints for later matching."""
    decision = outcome.decision
    rows = [ScreeningRecord(video=video, provider=item.provider, kind=item.kind, score=item.score,
                            reason=item.reason, segments=[list(span) for span in item.segments])
            for item in outcome.findings]
    rows.append(ScreeningRecord(video=video, provider="decision", kind="decision", action=decision.action,
                                score=max((item.score for item in outcome.findings), default=0.0),
                                reason=decision.reason, segments=[list(span) for span in decision.mute_segments]))
    ScreeningRecord.objects.bulk_create(rows)
    Fingerprint.objects.filter(video=video, blocked=False).delete()
    Fingerprint.objects.bulk_create([Fingerprint(video=video, kind=kind, value=value)
                                     for kind, value in outcome.fingerprints])


def _finish(upload, token, state, *, key=None, duration=None, poster=None, failure=None, outcome=None, screening_result=None):
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
            fields = ["state", "provider_asset_id", "duration_seconds", "duration_ms", "poster_asset_id"]
            if outcome is not None:
                _record(video, outcome)
            if screening_result is not None:
                screening_result["safety_hold"] = outcome is not None and outcome.decision.action != screening.PUBLISH
                automatic = copyright.route(video, reservation, screening_result)
                if automatic:
                    video.state = Video.State.PUBLISHED
                    video.visibility = Video.Visibility.PRIVATE
                    video.moderation_approved_at = timezone.now()
                    video.approval_source = "automated"
                    copyright.audit(video, "automatically_approved", "Clean unsampled upload under explicit trusted creator policy")
                else:
                    video.state = Video.State.REVIEW
                fields += ["state", "visibility", "moderation_approved_at", "approval_source", "rights_status"]
            video.save(update_fields=fields)
        video.failure_reason = failure
        video.save(update_fields=["failure_reason"])
        if failure:
            copyright.audit(video, "processing_failed", failure)
        reservation.lease_id = reservation.lease_until = None
        reservation.save(update_fields=["lease_id", "lease_until"])


def _screen(upload, source, playback, duration, directory):
    try:
        config = screening.load_config()
    except ValueError:
        config = screening.Config(enabled=True)  # a broken configuration must hold the video, not skip screening
    if not config.enabled:
        return None
    media = screening.Media(upload.video_id, upload.video.creator_id, source, playback, duration, Path(directory))
    return screening.evaluate(media, config)


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
            media = screening.Media(upload.video_id, upload.video.creator_id, source, destination, duration, Path(directory))
            screening_result = copyright.analyze(source, media=media)
            outcome = _screen(upload, source, destination, duration, directory)
            if outcome is not None and outcome.decision.mute_segments:
                muted = Path(directory) / "muted.mp4"
                try:
                    media_encoding.mute_segments(destination, muted, outcome.decision.mute_segments, duration)
                    destination = muted
                except media_encoding.InvalidMedia:
                    outcome = outcome.hold("mute_failed")
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
        _finish(upload, token, Video.State.REVIEW,
                key=key, duration=duration, poster=poster_key, outcome=outcome, screening_result=screening_result)
