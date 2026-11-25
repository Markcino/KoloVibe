from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from service.models import MediaUpload, Video

# A reservation is valid for ten minutes and processing can only start before it ends, so a video still processing a
# quarter of an hour after that point has been waiting at least that long. The lease is ten minutes, so a job a
# worker is actually running always holds one.
DEFAULT_STALLED_MINUTES = 15
MAX_LIMIT = 500


def stalled_uploads(now, stalled_minutes=DEFAULT_STALLED_MINUTES):
    """Processing videos with a stored source, no live lease, and past the stalled threshold. Read-only."""
    return (MediaUpload.objects.filter(video__state=Video.State.PROCESSING, video__deleted_at__isnull=True,
                                       expires_at__lt=now - timedelta(minutes=stalled_minutes))
            .exclude(source_etag="").filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now))
            .order_by("expires_at", "id"))


def posterless_videos():
    """Processed, undeleted videos whose poster was cleared by a cover edit and not yet re-rendered. Read-only."""
    from service.media_processing import PROCESSED_STATES

    return (Video.objects.filter(deleted_at__isnull=True, poster_asset_id__isnull=True, state__in=PROCESSED_STATES)
            .exclude(provider_asset_id__isnull=True).exclude(provider_asset_id="").order_by("created_at", "id"))


def requeue(now=None, *, limit=100, stalled_minutes=DEFAULT_STALLED_MINUTES, enqueue=None, enqueue_cover=None):
    """Re-publish the processing task for stalled videos; returns (requeued, failed) counts.

    Safe to repeat: the worker claims each video under a lease, so a duplicate message does nothing while another
    worker holds it, and a finished video is no longer in the processing state.
    """
    if not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"Limit must be between 1 and {MAX_LIMIT}")
    if not isinstance(stalled_minutes, int) or not 5 <= stalled_minutes <= 1440:
        raise ValueError("Stalled threshold must be between 5 and 1440 minutes")
    if enqueue is None:
        from service.media_api import _enqueue as enqueue
    if enqueue_cover is None:
        from service.media_api import _enqueue_cover as enqueue_cover
    now = now or timezone.now()
    requeued = failed = 0
    for video_id in list(stalled_uploads(now, stalled_minutes).values_list("video_id", flat=True)[:limit]):
        try:
            enqueue(video_id)
            requeued += 1
        except Exception:  # broker unavailable: leave it for the next run, never raise the identifier or message
            failed += 1
    # Cover renders share the budget: a render is idempotent while the poster is missing (D-P2-01).
    for video_id in list(posterless_videos().values_list("id", flat=True)[:max(0, limit - requeued - failed)]):
        try:
            enqueue_cover(video_id)
            requeued += 1
        except Exception:
            failed += 1
    return requeued, failed


class Command(BaseCommand):
    help = ("Re-publish the processing task for videos stuck in `processing` (lost broker message or exhausted "
            "retries) and the cover render for processed videos left without a poster. Prints counts only; safe to "
            "repeat.")

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--stalled-minutes", type=int, default=DEFAULT_STALLED_MINUTES)

    def handle(self, *args, **options):
        try:
            requeued, failed = requeue(limit=options["limit"], stalled_minutes=options["stalled_minutes"])
        except ValueError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"requeued: {requeued}")
        self.stdout.write(f"failed: {failed}")
