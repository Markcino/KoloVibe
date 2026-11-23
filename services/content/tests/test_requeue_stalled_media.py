from datetime import timedelta
from io import StringIO
from uuid import uuid4

from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from service.management.commands.requeue_stalled_media import requeue, stalled_uploads
from service.models import MediaUpload, Video


class RequeueStalledMediaTests(TestCase):
    def setUp(self):
        self.now = timezone.now()

    def upload(self, *, state=Video.State.PROCESSING, expired_minutes=60, etag='"stored"', lease=None, deleted=False):
        video = Video.objects.create(creator_id=uuid4(), title="Original", state=state,
                                     deleted_at=self.now if deleted else None)
        MediaUpload.objects.create(id=uuid4(), video=video, expected_bytes=10, source_etag=etag,
                                   expires_at=self.now - timedelta(minutes=expired_minutes),
                                   lease_id=uuid4() if lease is not None else None, lease_until=lease)
        return video

    def ids(self, **kwargs):
        return set(stalled_uploads(self.now, **kwargs).values_list("video_id", flat=True))

    def test_only_stalled_processing_videos_without_a_live_lease_are_selected(self):
        stalled = self.upload()
        expired_lease = self.upload(lease=self.now - timedelta(minutes=1))
        self.upload(lease=self.now + timedelta(minutes=5))              # a worker is running it
        self.upload(expired_minutes=3)                                   # not stalled yet
        self.upload(etag="")                                             # source never confirmed
        self.upload(deleted=True)                                        # deleted by the creator
        for state in (Video.State.DRAFT, Video.State.UPLOADING, Video.State.FAILED, Video.State.REVIEW,
                      Video.State.PUBLISHED, Video.State.REJECTED, Video.State.REMOVED):
            if state != Video.State.PUBLISHED:
                self.upload(state=state)
        self.assertEqual(self.ids(), {stalled.id, expired_lease.id})

    def test_requeue_publishes_each_stalled_video_once_and_respects_the_limit(self):
        videos = [self.upload(expired_minutes=60 + number) for number in range(3)]
        sent = []
        self.assertEqual(requeue(self.now, limit=2, enqueue=sent.append), (2, 0))
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0], videos[2].id, "oldest reservation first")
        sent.clear()
        self.assertEqual(requeue(self.now, limit=10, enqueue=sent.append), (3, 0))
        self.assertEqual(set(sent), {video.id for video in videos})

    def test_a_broker_failure_is_counted_not_raised_and_leaves_the_video_for_the_next_run(self):
        video = self.upload()

        def broken(video_id):
            raise OSError("broker address and credentials must never surface")

        self.assertEqual(requeue(self.now, enqueue=broken), (0, 1))
        self.assertEqual(self.ids(), {video.id})
        video.refresh_from_db()
        self.assertEqual(video.state, Video.State.PROCESSING, "requeue never changes video state")

    def test_requeue_is_read_only_for_the_database(self):
        self.upload()
        before = list(MediaUpload.objects.values_list("id", "lease_id", "lease_until", "source_etag"))
        requeue(self.now, enqueue=lambda video_id: None)
        self.assertEqual(list(MediaUpload.objects.values_list("id", "lease_id", "lease_until", "source_etag")), before)

    def test_limits_are_validated(self):
        for bad in (0, -1, 501, "5", None):
            with self.subTest(limit=bad), self.assertRaises(ValueError):
                requeue(self.now, limit=bad, enqueue=lambda video_id: None)
        for bad in (4, 1441, "15"):
            with self.subTest(minutes=bad), self.assertRaises(ValueError):
                requeue(self.now, stalled_minutes=bad, enqueue=lambda video_id: None)

    def test_command_reports_counts_only(self):
        self.upload()
        out = StringIO()
        from unittest.mock import patch

        with patch("service.media_api._enqueue") as enqueue:
            call_command("requeue_stalled_media", stdout=out)
        enqueue.assert_called_once()
        self.assertEqual(out.getvalue().split(), ["requeued:", "1", "failed:", "0"])
        with self.assertRaises(CommandError):
            call_command("requeue_stalled_media", "--limit", "0", stdout=StringIO())
