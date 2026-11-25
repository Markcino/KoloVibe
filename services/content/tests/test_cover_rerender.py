"""D-P2-01: a cover edit on a processed video must lead to a new poster, never to a permanent loss of it."""

from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import media_encoding, media_storage
from service.management.commands.requeue_stalled_media import requeue, posterless_videos
from service.media_api import media_api
from service.media_processing import render_cover
from service.models import Video


class CoverRerenderTests(TestCase):
    def setUp(self):
        self.creator = uuid4()
        now = timezone.now()
        self.video = Video.objects.create(
            creator_id=self.creator, title="Original", category="hipco", state="published", visibility="public",
            provider_asset_id=f"playback/{uuid4()}/{uuid4()}.mp4", poster_asset_id="playback/old/poster.jpg",
            moderation_approved_at=now, published_at=now, duration_ms=4000, duration_seconds=4)

    def edit(self, fields):
        request = RequestFactory().post("/internal/videos/media/edit", {
            "creator_id": str(self.creator), "video_id": str(self.video.id), **fields}, content_type="application/json")
        request.service_caller = "gateway"
        return media_api(request, "edit")

    def test_cover_edit_on_a_processed_video_queues_one_render_after_commit(self):
        with patch("service.media_api._enqueue_cover") as enqueue, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.edit({"cover_time_ms": 2000}).status_code, 200)
        enqueue.assert_called_once_with(self.video.id)
        self.video.refresh_from_db()
        self.assertIsNone(self.video.poster_asset_id)
        self.assertEqual(self.video.state, "published")

    def test_other_edits_and_unprocessed_drafts_queue_nothing(self):
        with patch("service.media_api._enqueue_cover") as enqueue, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.edit({"title": "Renamed"}).status_code, 200)
        enqueue.assert_not_called()
        draft = Video.objects.create(creator_id=self.creator, title="Draft", category="hipco")
        self.video = draft
        with patch("service.media_api._enqueue_cover") as enqueue, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.edit({"cover_time_ms": 0}).status_code, 200)
        enqueue.assert_not_called()

    def test_a_broker_outage_does_not_fail_the_saved_edit(self):
        with patch("service.media_api._enqueue_cover", side_effect=OSError), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.edit({"cover_time_ms": 1000}).status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual(self.video.cover_time_ms, 1000)

    @patch("service.media_storage.put_poster")
    @patch("service.media_encoding.render_poster")
    @patch("service.media_storage.download_playback")
    def test_render_reads_the_private_rendition_and_stores_a_new_poster(self, download, render, put):
        Video.objects.filter(pk=self.video.pk).update(poster_asset_id=None, cover_time_ms=2500)
        self.assertTrue(render_cover(self.video.id))
        self.assertEqual(download.call_args.args[0], self.video.provider_asset_id)
        self.assertEqual(render.call_args.args[2:], (2500, 4000))
        self.video.refresh_from_db()
        self.assertTrue(self.video.poster_asset_id.startswith(f"posters/{self.video.id}/"))
        self.assertEqual(put.call_args.args[0], self.video.poster_asset_id)
        self.assertEqual((self.video.state, self.video.visibility), ("published", "public"))

    @patch("service.media_storage.put_poster")
    @patch("service.media_encoding.render_poster")
    @patch("service.media_storage.download_playback")
    def test_render_is_a_no_op_for_a_video_with_a_poster_deleted_or_unprocessed(self, download, render, put):
        self.assertFalse(render_cover(self.video.id))
        Video.objects.filter(pk=self.video.pk).update(poster_asset_id=None, deleted_at=timezone.now())
        self.assertFalse(render_cover(self.video.id))
        draft = Video.objects.create(creator_id=self.creator, title="Draft", category="hipco")
        self.assertFalse(render_cover(draft.id))
        self.assertFalse(render_cover(uuid4()))
        download.assert_not_called()

    @patch("service.media_storage.put_poster")
    @patch("service.media_encoding.render_poster")
    @patch("service.media_storage.download_playback")
    def test_a_newer_cover_edit_during_rendering_discards_the_stale_frame(self, download, render, put):
        Video.objects.filter(pk=self.video.pk).update(poster_asset_id=None, cover_time_ms=1000)

        def edited_meanwhile(*args):
            Video.objects.filter(pk=self.video.pk).update(cover_time_ms=3000)
        render.side_effect = edited_meanwhile
        self.assertFalse(render_cover(self.video.id))
        self.video.refresh_from_db()
        self.assertIsNone(self.video.poster_asset_id)

    @patch("service.media_storage.put_poster")
    @patch("service.media_encoding.render_poster", side_effect=media_encoding.InvalidMedia)
    @patch("service.media_storage.download_playback")
    def test_an_unrenderable_frame_keeps_the_video_playable(self, download, render, put):
        Video.objects.filter(pk=self.video.pk).update(poster_asset_id=None, cover_time_ms=1000)
        self.assertFalse(render_cover(self.video.id))
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.provider_asset_id is not None), ("published", True))
        put.assert_not_called()

    @patch("service.media_storage.download_playback", side_effect=media_storage.StorageUnavailable)
    def test_storage_outage_is_raised_for_retry(self, download):
        Video.objects.filter(pk=self.video.pk).update(poster_asset_id=None)
        with self.assertRaises(media_storage.StorageUnavailable):
            render_cover(self.video.id)

    def test_recovery_requeues_processed_videos_left_without_a_poster(self):
        Video.objects.filter(pk=self.video.pk).update(poster_asset_id=None)
        Video.objects.create(creator_id=self.creator, title="Draft", category="hipco")
        Video.objects.create(creator_id=self.creator, title="Gone", category="hipco", state="rejected",
                             provider_asset_id="playback/a/b.mp4", deleted_at=timezone.now())
        Video.objects.create(creator_id=self.creator, title="Busy", category="hipco", state="processing",
                             provider_asset_id="playback/c/d.mp4")
        self.assertEqual(list(posterless_videos().values_list("id", flat=True)), [self.video.id])
        covers = []
        with patch("service.media_api._enqueue") as enqueue:
            requeued, failed = requeue(limit=10, enqueue_cover=covers.append)
        enqueue.assert_not_called()
        self.assertEqual((requeued, failed, covers), (1, 0, [self.video.id]))

    def test_recovery_counts_a_broker_failure_without_raising(self):
        Video.objects.filter(pk=self.video.pk).update(poster_asset_id=None)

        def down(video_id):
            raise OSError
        with patch("service.media_api._enqueue"):
            self.assertEqual(requeue(limit=10, enqueue_cover=down), (0, 1))
