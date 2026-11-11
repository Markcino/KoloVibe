import json
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.likes import read_like, update_like
from service.models import VideoLike


class VideoLikeTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.video_id = str(uuid4())
        self.account_id = str(uuid4())

    def write_like(self, liked, account_id=None, caller="gateway"):
        request = self.factory.post("/internal/likes", data=json.dumps({
            "video_id": self.video_id, "account_id": account_id or self.account_id, "liked": liked,
        }), content_type="application/json")
        request.service_caller = caller
        return update_like(request)

    def test_repeat_likes_and_removals_are_idempotent_and_isolated(self):
        other_account = str(uuid4())
        self.assertEqual(self.write_like(True).status_code, 200)
        self.assertEqual(self.write_like(True).status_code, 200)
        self.assertEqual(self.write_like(True, other_account).status_code, 200)
        self.assertEqual(VideoLike.objects.count(), 2)

        self.assertEqual(self.write_like(False).status_code, 204)
        self.assertEqual(self.write_like(False).status_code, 204)
        self.assertEqual(str(VideoLike.objects.get().account_id), other_account)

    def test_only_gateway_can_write_and_the_intent_must_be_boolean(self):
        self.assertEqual(self.write_like(True, caller="identity").status_code, 403)
        self.assertEqual(self.write_like(1).status_code, 400)
        self.assertFalse(VideoLike.objects.exists())

    def test_status_is_scoped_to_account_and_requires_gateway(self):
        self.write_like(True)
        def status(account_id, caller="gateway"):
            request = self.factory.post("/internal/likes/status", data=json.dumps({
                "video_id": self.video_id, "account_id": account_id,
            }), content_type="application/json")
            request.service_caller = caller
            return read_like(request)
        self.assertEqual(json.loads(status(self.account_id).content)["liked"], True)
        self.assertEqual(json.loads(status(str(uuid4())).content)["liked"], False)
        self.assertEqual(status(self.account_id, caller="identity").status_code, 403)
