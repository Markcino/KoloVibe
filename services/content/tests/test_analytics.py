import json
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.analytics import content_analytics
from service.models import Video


class ContentAnalyticsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.creator = uuid4()
        self.other = uuid4()

    def call(self, operation, data, caller="gateway"):
        request = self.factory.post("/internal/videos/analytics/" + operation,
                                    data, content_type="application/json")
        request.service_caller = caller
        return content_analytics(request, operation)

    def test_summary_counts_only_owned_actual_videos(self):
        Video.objects.create(creator_id=self.creator, title="Own draft")
        Video.objects.create(creator_id=self.creator, title="Own review", state=Video.State.REVIEW)
        Video.objects.create(creator_id=self.other, title="Other draft")
        response = self.call("summary", {"creator_id": str(self.creator)})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total_videos"], 2)
        self.assertEqual(data["videos_by_state"]["draft"], 1)
        self.assertEqual(data["videos_by_state"]["review"], 1)
        self.assertEqual(data["videos_by_state"]["published"], 0)
        self.assertEqual(self.call("summary", {"creator_id": str(self.creator)}, caller="identity").status_code, 403)

    def test_video_read_enforces_creator_ownership(self):
        owned = Video.objects.create(creator_id=self.creator, title="Owned")
        foreign = Video.objects.create(creator_id=self.other, title="Private")
        self.assertEqual(self.call("video", {"creator_id": str(self.creator),
                                             "video_id": str(owned.id)}).status_code, 200)
        self.assertEqual(self.call("video", {"creator_id": str(self.creator),
                                             "video_id": str(foreign.id)}).status_code, 404)
        self.assertEqual(self.call("video", {"creator_id": str(self.creator),
                                             "video_id": str(uuid4())}).status_code, 404)
        self.assertEqual(self.call("video", {"creator_id": str(self.creator),
                                             "video_id": "bad"}).status_code, 400)
