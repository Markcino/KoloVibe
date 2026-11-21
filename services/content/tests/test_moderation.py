from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.models import ModerationReceipt, Video
from service.media_api import media_api
from service.moderation import moderation_video


class ModerationContentTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.video = Video.objects.create(creator_id=uuid4(), title="Original", state=Video.State.REVIEW,
                                          provider_asset_id="fixture-processed-asset")

    def apply(self, action, revision, action_id, caller="moderation"):
        request = self.factory.post("/internal/videos/moderation/apply", {
            "video_id": str(self.video.id), "action": action, "revision": revision, "action_id": str(action_id),
        }, content_type="application/json")
        request.service_caller = caller
        return moderation_video(request, "apply")

    def test_review_approval_stays_private_until_creator_publishes(self):
        publish, removal, restore = uuid4(), uuid4(), uuid4()

        self.assertEqual(self.apply("publish", 0, publish, caller="gateway").status_code, 403)
        self.assertEqual(self.apply("publish", 0, publish).status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility, self.video.moderation_revision),
                         ("published", "private", 1))
        self.assertIsNotNone(self.video.moderation_approved_at)
        self.assertIsNone(self.video.published_at)

        # Approval alone must not allow removal from a public video state.
        self.assertEqual(self.apply("remove", 1, removal).status_code, 409)

        request = self.factory.post("/internal/videos/media/publish", {
            "creator_id": str(self.video.creator_id), "video_id": str(self.video.id),
        }, content_type="application/json")
        request.service_caller = "gateway"
        self.assertEqual(media_api(request, "publish").status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual((self.video.visibility, self.video.moderation_revision),
                         ("public", 2))
        self.assertIsNotNone(self.video.published_at)
        original_published_at = self.video.published_at

        self.assertEqual(self.apply("remove", 2, removal).status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility), ("removed", "private"))

        # Appeal restoration of a previously public video retains prior behavior.
        self.assertEqual(self.apply("restore", 3, restore).status_code, 200)
        self.assertEqual(self.apply("remove", 2, removal).status_code, 200)
        self.assertEqual(self.apply("remove", 2, uuid4()).status_code, 409)
        self.assertEqual(self.apply("remove", 4, removal).status_code, 409)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility, self.video.moderation_revision),
                         ("published", "public", 4))
        self.assertEqual(self.video.published_at, original_published_at)
        self.assertEqual(ModerationReceipt.objects.count(), 3)

    def test_unprocessed_draft_cannot_be_published(self):
        self.video.state = Video.State.DRAFT
        self.video.save(update_fields=["state"])
        self.assertEqual(self.apply("publish", 0, uuid4()).status_code, 409)
        self.assertFalse(ModerationReceipt.objects.exists())

    def test_queue_filters_explicit_assignment_scope_before_pagination(self):
        import json
        other = Video.objects.create(creator_id=uuid4(), title="Other", state=Video.State.REVIEW)
        request = self.factory.post("/internal/videos/moderation/queue", {
            "cursor": None, "scope_ids": [str(self.video.id)]}, content_type="application/json")
        request.service_caller = "moderation"
        response = moderation_video(request, "queue")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["items"], [{"id": str(self.video.id), "title": "Original"}])
        self.assertNotIn(str(other.id).encode(), response.content)


    def test_reviewer_detail_and_preview_are_moderation_only(self):
        import json
        from unittest.mock import patch
        self.video.provider_asset_id = f"playback/{uuid4()}/{uuid4()}.mp4"
        self.video.save(update_fields=["provider_asset_id"])
        for operation in ("detail", "preview"):
            request = self.factory.post("/internal/videos/moderation/" + operation,
                {"video_id": str(self.video.id)}, content_type="application/json")
            request.service_caller = "gateway"
            self.assertEqual(moderation_video(request, operation).status_code, 403)
            request.service_caller = "moderation"
            with patch("service.moderation.storage.read_preview", return_value=b"mp4"):
                response = moderation_video(request, operation)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(self.video.provider_asset_id.encode(), response.content)
            if operation == "detail":
                self.assertEqual(json.loads(response.content)["rights_status"], "not_recorded")


    def test_status_counts_match_filtered_records(self):
        import json
        for operation, data in (("totals", {"scope_ids": [str(self.video.id)]}),
                                ("queue", {"cursor": None, "status": "rejected"})):
            request = self.factory.post("/internal/videos/moderation/" + operation, data, content_type="application/json")
            request.service_caller = "moderation"
            result = moderation_video(request, operation)
            self.assertEqual(result.status_code, 200)
            if operation == "totals":
                self.assertEqual(json.loads(result.content), {"review": 1, "published": 0, "rejected": 0, "removed": 0})
            else:
                self.assertEqual(json.loads(result.content)["items"], [])
