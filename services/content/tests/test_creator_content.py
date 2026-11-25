from datetime import timedelta
import json
from unittest.mock import patch
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import media_encoding, media_storage
from service.analytics import content_analytics
from service.media_api import media_api
from service.media_processing import _claim, _finish, process
from service.models import MediaUpload, Video
from service.moderation import moderation_video
from service.videos import internal_lookup, internal_published_count, _public_videos
from service.videos import _list_videos


class CreatorContentTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.creator = uuid4()
        self.video = Video.objects.create(creator_id=self.creator, title="Original", category="hipco")
        self.owner = {"creator_id": str(self.creator), "video_id": str(self.video.id)}

    def request(self, path, data, caller="gateway"):
        request = self.factory.post(path, data, content_type="application/json")
        request.service_caller = caller
        return request

    def call(self, operation, fields=None):
        if operation == "intent":
            fields = {"account_id": str(self.creator), "originality_attestation": {"version": "R1-originality-v1", "accepted": True},
                      "review_policy": {"trusted": False, "sample_percent": 100, "policy_version": None}, **(fields or {})}
        return media_api(self.request("/internal/videos/media/" + operation, self.owner | (fields or {})), operation)

    def publish(self):
        now = timezone.now()
        Video.objects.filter(pk=self.video.pk).update(
            state="published", visibility="public", provider_asset_id=f"playback/{uuid4()}/{uuid4()}.mp4",
            moderation_approved_at=now, published_at=now, duration_ms=2000, duration_seconds=2)
        self.video.refresh_from_db()

    def test_draft_category_is_required_and_tags_are_normalized_bounded_and_unique(self):
        path = "/internal/videos/media/draft"
        base = {"creator_id": str(self.creator), "title": " New original "}
        self.assertEqual(media_api(self.request(path, base), "draft").status_code, 400)
        result = media_api(self.request(path, base | {"category": "culture", "tags": ["#Monrovia", " hipco ", "HIPCO"]}), "draft")
        self.assertEqual(result.status_code, 201)
        data = json.loads(result.content)
        self.assertEqual((data["title"], data["category"], data["tags"]), ("New original", "culture", ["monrovia", "hipco"]))
        self.assertEqual((data["visibility"], data["published_at"], data["poster_url"]), ("private", None, None))
        for values in ({"category": None}, {"category": "unknown"}, {"tags": ["x"] * 6}, {"tags": "hipco"},
                       {"tags": ["has space"]}, {"tags": ["x" * 31]}, {"cover_time_ms": True}, {"cover_time_ms": -1}):
            result = media_api(self.request(path, base | {"category": "hipco"} | values), "draft")
            self.assertEqual(result.status_code, 400)

    def test_partial_edits_allow_requested_states_and_preserve_public_approval(self):
        self.publish()
        approved = self.video.moderation_approved_at
        with patch("service.media_storage.sign_playback", return_value="https://signed.invalid/poster"):
            Video.objects.filter(pk=self.video.pk).update(poster_asset_id=f"playback/{uuid4()}/{uuid4()}.jpg")
            result = self.call("edit", {"title": "Updated", "category": "comedy", "tags": ["#Hipco"], "cover_time_ms": 2000})
        self.assertEqual(result.status_code, 200)
        data = json.loads(result.content)
        self.assertEqual((data["state"], data["visibility"], data["poster_url"]), ("published", "public", None))
        # Decision A: the reviewed text stays live and the edit waits for review; the cover applies at once.
        self.assertEqual((data["title"], data["category"], data["tags"], data["cover_time_ms"]), ("Original", "hipco", [], 2000))
        self.assertEqual(data["edit_review"]["proposed"], {"title": "Updated", "description": "", "category": "comedy", "tags": ["hipco"]})
        self.video.refresh_from_db()
        self.assertEqual(self.video.moderation_approved_at, approved)
        self.assertEqual(self.video.moderation_revision, 1)
        self.assertEqual(self.call("edit", {"cover_time_ms": 2001}).status_code, 400)
        for state in ("draft", "failed", "rejected"):
            Video.objects.filter(pk=self.video.pk).update(state=state, visibility="private")
            self.assertEqual(self.call("edit", {"description": state}).status_code, 200)
        for state in ("uploading", "processing", "review", "removed"):
            Video.objects.filter(pk=self.video.pk).update(state=state)
            self.assertEqual(self.call("edit", {"description": "Cannot edit"}).status_code, 409)

    def test_cover_duration_database_guard_and_existing_null_category(self):
        legacy = Video.objects.create(creator_id=self.creator, title="Legacy")
        self.assertIsNone(legacy.category)
        legacy.duration_seconds = 1
        legacy.save(update_fields=["duration_seconds"])
        self.assertEqual(self.call("edit", {"video_id": str(legacy.id), "cover_time_ms": 1001}).status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Video.objects.filter(pk=self.video.pk).update(duration_ms=500, cover_time_ms=501)

    def test_category_filter_and_cursor_are_scoped_to_public_non_deleted_rows(self):
        self.publish()
        other = Video.objects.create(creator_id=self.creator, title="Comedy", category="comedy", state="published",
                                    visibility="public", provider_asset_id="comedy", moderation_approved_at=timezone.now())
        Video.objects.create(creator_id=self.creator, title="Hidden", category="hipco")
        response = _list_videos(str(self.creator), None, "original", "hipco")
        self.assertEqual([item["id"] for item in json.loads(response.content)["items"]], [str(self.video.id)])
        self.assertEqual(_list_videos(None, str(other.id), None, "hipco").status_code, 400)
        self.assertEqual(_list_videos(None, None, None, "other").status_code, 400)

    def test_soft_delete_is_available_in_every_owned_state(self):
        for state in Video.State.values:
            values = {"creator_id": self.creator, "title": state, "state": state}
            if state == "published":
                values.update(provider_asset_id="retained-object", moderation_approved_at=timezone.now())
            video = Video.objects.create(**values)
            self.assertEqual(self.call("delete", {"video_id": str(video.id)}).status_code, 200)
            video.refresh_from_db()
            self.assertIsNotNone(video.deleted_at)
            self.assertEqual(video.state, state)

    @patch("service.media_storage.download_upload", side_effect=media_storage.StorageUnavailable)
    def test_transient_worker_failure_retains_retryable_processing_without_leaking_details(self, download):
        Video.objects.filter(pk=self.video.pk).update(state="processing")
        MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
                                   expires_at=timezone.now(), source_etag='"object"')
        with self.assertRaises(media_storage.StorageUnavailable):
            process(self.video.id)
        status = json.loads(self.call("status").content)
        self.assertEqual(status, {"video_id": str(self.video.id), "state": "processing",
                                  "failure_reason": "processing_unavailable", "retryable": True})
        self.assertIsNone(MediaUpload.objects.get().lease_id)

    def test_unpublish_is_idempotent_and_publish_requires_private_approval(self):
        result = self.call("publish")
        self.assertEqual(result.status_code, 409)
        self.assertEqual(json.loads(result.content)["code"], "review_required")
        self.publish()
        published_at = self.video.published_at
        self.assertEqual(self.call("unpublish").status_code, 200)
        self.assertEqual(self.call("unpublish").status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility, self.video.moderation_revision), ("published", "private", 1))
        self.assertFalse(_public_videos().filter(pk=self.video.pk).exists())
        self.assertEqual(self.call("publish").status_code, 200)
        self.assertEqual(self.call("publish").status_code, 409)
        self.video.refresh_from_db()
        self.assertEqual(self.video.moderation_revision, 2)
        self.assertEqual(self.video.published_at, published_at)

    def test_all_owned_operations_return_404_for_another_creator(self):
        for operation, fields in (("edit", {"title": "Stolen"}), ("delete", {}), ("publish", {}),
                                  ("unpublish", {}), ("detail", {}), ("status", {}), ("complete", {}),
                                  ("intent", {"size_bytes": 10, "idempotency_key": "foreign-upload-001"})):
            response = self.call(operation, fields | {"creator_id": str(uuid4())})
            self.assertEqual(response.status_code, 404)

    def test_library_state_groups_cursor_and_metadata(self):
        for state in Video.State.values:
            values = {"creator_id": self.creator, "title": state, "state": state}
            if state == "published":
                values.update(provider_asset_id="legacy-asset", moderation_approved_at=timezone.now())
            Video.objects.create(**values)
        Video.objects.create(creator_id=uuid4(), title="Foreign")
        base = {"creator_id": str(self.creator), "cursor": None}
        def library(fields):
            return media_api(self.request("/internal/videos/media/library", base | fields), "library")
        result = json.loads(library({"state": "in_progress"}).content)
        self.assertEqual({item["state"] for item in result["items"]}, {"uploading", "processing"})
        self.assertEqual(library({"state": "uploading"}).status_code, 400)
        for state in ("draft", "review", "published", "rejected", "removed", "failed"):
            result = json.loads(library({"state": state}).content)
            self.assertTrue(all(item["state"] == state for item in result["items"]))
            self.assertTrue(all({"visibility", "published_at", "poster_url", "category", "tags"} <= item.keys() for item in result["items"]))
        foreign = Video.objects.create(creator_id=uuid4(), title="Foreign cursor")
        self.assertEqual(library({"cursor": str(foreign.id)}).status_code, 400)

    def test_library_search_matches_only_own_undeleted_videos_and_composes_with_state_and_cursor(self):
        mine = {"creator_id": self.creator}
        Video.objects.create(**mine, title="River Song", description="a short film", state="published",
                             provider_asset_id="legacy-asset", moderation_approved_at=timezone.now())
        Video.objects.create(**mine, title="Skit night", description="about the RIVER", state="draft")
        Video.objects.create(**mine, title="Unrelated", description="nothing", state="draft")
        Video.objects.create(**mine, title="100% river_run", description="literal wildcard characters", state="draft")
        Video.objects.create(**mine, title="river deleted", state="draft", deleted_at=timezone.now())
        Video.objects.create(creator_id=uuid4(), title="river of someone else", state="published",
                             provider_asset_id="legacy-asset-foreign", moderation_approved_at=timezone.now())
        base = {"creator_id": str(self.creator), "cursor": None}

        def library(fields):
            return media_api(self.request("/internal/videos/media/library", base | fields), "library")

        titles = lambda fields: [item["title"] for item in json.loads(library(fields).content)["items"]]
        self.assertEqual(set(titles({"q": " river "})), {"River Song", "Skit night", "100% river_run"})
        self.assertEqual(titles({"q": "RIVER", "state": "published"}), ["River Song"])
        self.assertEqual(titles({"q": "100%"}), ["100% river_run"], "% is literal, not a wildcard")
        self.assertEqual(titles({"q": "_"}), ["100% river_run"], "_ is literal, not a wildcard")
        self.assertEqual(titles({"q": "no such text"}), [])
        # A cursor must belong to the same filtered view; one from outside it is rejected, never leaked.
        everything = json.loads(library({}).content)["items"]
        outside = next(item for item in everything if item["title"] == "Unrelated")
        self.assertEqual(library({"q": "river", "cursor": outside["id"]}).status_code, 400)
        for bad in ("", "   ", "x" * 101, "bad\x00query", 5, ["river"]):
            with self.subTest(q=bad):
                self.assertEqual(library({"q": bad}).status_code, 400)

    def test_deleted_video_is_hidden_in_every_read_and_moderation_cannot_restore_it(self):
        self.publish()
        reservation = MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
            expires_at=timezone.now() + timedelta(minutes=5), source_etag='"object"', lease_id=uuid4(), lease_until=timezone.now())
        source_key = reservation.source_key
        self.assertEqual(self.call("delete").status_code, 200)
        self.video.refresh_from_db(); reservation.refresh_from_db()
        self.assertIsNotNone(self.video.deleted_at)
        self.assertEqual(self.video.visibility, "private")
        self.assertEqual(reservation.source_key, source_key)
        self.assertIsNone(reservation.lease_id)
        self.assertLessEqual(reservation.expires_at, timezone.now())
        for operation in ("detail", "status", "complete", "playback", "watch", "watch-check"):
            fields = {"video_id": str(self.video.id)} if operation in {"playback", "watch", "watch-check"} else self.owner
            self.assertEqual(media_api(self.request("/internal/test", fields), operation).status_code, 404)
        self.assertEqual(_public_videos().count(), 0)
        request = self.request("/internal/videos/moderation/inspect", {"video_id": str(self.video.id)}, "moderation")
        self.assertEqual(moderation_video(request, "inspect").status_code, 404)
        request = self.request("/internal/videos/moderation/apply", {"video_id": str(self.video.id), "action_id": str(uuid4()),
                               "action": "restore", "revision": self.video.moderation_revision}, "moderation")
        self.assertEqual(moderation_video(request, "apply").status_code, 404)
        result = content_analytics(self.request("/internal/videos/analytics/summary", {"creator_id": str(self.creator)}), "summary")
        self.assertEqual(json.loads(result.content)["total_videos"], 0)

    @patch("service.media_storage.sign_upload", return_value="https://signed.invalid/upload")
    def test_retry_replaces_reservation_and_clears_failure_without_purging_storage(self, sign):
        first = self.call("intent", {"size_bytes": 10, "idempotency_key": "initial-upload-001"})
        first_id = json.loads(first.content)["upload_id"]
        Video.objects.filter(pk=self.video.pk).update(state="failed", failure_reason="invalid_media")
        status = json.loads(self.call("status").content)
        self.assertEqual((status["failure_reason"], status["retryable"]), ("invalid_media", True))
        self.assertEqual(self.call("intent", {"size_bytes": 10, "idempotency_key": "initial-upload-001"}).status_code, 409)
        second = self.call("intent", {"size_bytes": 11, "idempotency_key": "retried-upload-002"})
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(json.loads(second.content)["upload_id"], first_id)
        self.assertEqual(MediaUpload.objects.count(), 1)
        status = json.loads(self.call("status").content)
        self.assertEqual((status["state"], status["failure_reason"], status["retryable"]), ("uploading", None, True))

    def test_lookup_preserves_order_and_count_excludes_hidden_rows(self):
        self.publish()
        second = Video.objects.create(creator_id=self.creator, title="Second", state="published", visibility="public",
                                      provider_asset_id="second", moderation_approved_at=timezone.now(), category="comedy")
        private = Video.objects.create(creator_id=self.creator, title="Private")
        deleted = Video.objects.create(creator_id=self.creator, title="Deleted", state="published", visibility="public",
                                       provider_asset_id="deleted", moderation_approved_at=timezone.now(), deleted_at=timezone.now())
        ids = [str(second.id), str(private.id), str(uuid4()), str(self.video.id), str(deleted.id)]
        result = internal_lookup(self.request("/internal/videos/lookup", {"ids": ids}))
        self.assertEqual([item["id"] for item in json.loads(result.content)["items"]], [str(second.id), str(self.video.id)])
        result = internal_published_count(self.request("/internal/videos/published-count", {"creator_id": str(self.creator)}))
        self.assertEqual(json.loads(result.content)["published_video_count"], 2)
        for data in ({"ids": [str(uuid4())] * 51}, {"ids": "bad"}, {"ids": [None]}, {"ids": [], "extra": True}):
            self.assertEqual(internal_lookup(self.request("/internal/videos/lookup", data)).status_code, 400)
        self.assertEqual(internal_lookup(self.request("/internal/videos/lookup", {"ids": []}, "engagement")).status_code, 403)

    def test_deleted_processing_video_cannot_be_claimed_or_finished(self):
        Video.objects.filter(pk=self.video.pk).update(state="processing")
        upload = MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
                                           expires_at=timezone.now(), source_etag='"object"')
        claimed, token = _claim(self.video.id)
        self.assertEqual(self.call("delete").status_code, 200)
        self.assertIsNone(_claim(self.video.id))
        _finish(claimed, token, Video.State.REVIEW, key="orphan-private-object", duration=1000)
        self.video.refresh_from_db()
        self.assertEqual(self.video.state, "processing")
        self.assertIsNone(self.video.provider_asset_id)

    @patch("service.media_storage.download_upload")
    @patch("service.media_encoding.encode", return_value=500)
    @patch("service.media_encoding.render_poster")
    @patch("service.media_storage.put_playback")
    @patch("service.media_storage.put_poster")
    def test_short_clip_default_cover_and_out_of_range_failure(self, put_poster, put, render, encode, download):
        download.side_effect = lambda key, etag, size, destination: destination.write_bytes(b"short clip fixture")
        Video.objects.filter(pk=self.video.pk).update(state="processing")
        MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10, expires_at=timezone.now(), source_etag='"object"')
        process(self.video.id)
        self.assertEqual(render.call_args.args[2:], (0, 500))
        self.video.refresh_from_db()
        self.assertEqual(self.video.state, "review")
        Video.objects.filter(pk=self.video.pk).update(state="processing", duration_ms=None, cover_time_ms=501)
        process(self.video.id)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.failure_reason), ("failed", "cover_out_of_range"))
