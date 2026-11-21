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
