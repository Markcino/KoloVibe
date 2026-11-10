from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.models import ModerationReceipt, Video
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

    def test_publish_remove_restore_and_replay_keep_the_current_state(self):
        publish, removal, restore = uuid4(), uuid4(), uuid4()
        self.assertEqual(self.apply("publish", 0, publish, caller="gateway").status_code, 403)
        self.assertEqual(self.apply("publish", 0, publish).status_code, 200)
        self.assertEqual(self.apply("remove", 1, removal).status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility), ("removed", "private"))
        self.assertEqual(self.apply("restore", 2, restore).status_code, 200)
        self.assertEqual(self.apply("remove", 1, removal).status_code, 200)
        self.assertEqual(self.apply("remove", 1, uuid4()).status_code, 409)
        self.assertEqual(self.apply("remove", 3, removal).status_code, 409)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility, self.video.moderation_revision),
                         ("published", "public", 3))
        self.assertEqual(ModerationReceipt.objects.count(), 3)

    def test_unprocessed_draft_cannot_be_published(self):
        self.video.state = Video.State.DRAFT
        self.video.save(update_fields=["state"])
        self.assertEqual(self.apply("publish", 0, uuid4()).status_code, 409)
        self.assertFalse(ModerationReceipt.objects.exists())
