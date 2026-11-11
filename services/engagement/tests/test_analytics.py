import json
from datetime import timedelta
from uuid import uuid4

from django.test import RequestFactory, TestCase
from django.utils import timezone

from service.analytics import video_engagement
from service.models import VideoLike, WatchSession


class VideoEngagementAnalyticsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.video = uuid4()

    def call(self, data, caller="gateway"):
        request = self.factory.post("/internal/engagement/analytics/video", data,
                                    content_type="application/json")
        request.service_caller = caller
        return video_engagement(request)

    def test_counts_current_likes_and_distinct_qualified_accounts(self):
        now = timezone.now()
        for index in range(2):
            VideoLike.objects.create(video_id=self.video, account_id=uuid4())
            WatchSession.objects.create(
                video_id=self.video, account_id=uuid4(), creator_user_id=uuid4(),
                duration_ms=30000, revision=1, started_at=now,
                last_sample_at=now, expires_at=now + timedelta(seconds=90),
                qualified_at=now if index == 0 else None,
            )
        VideoLike.objects.create(video_id=uuid4(), account_id=uuid4())
        response = self.call({"video_id": str(self.video)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {
            "video_id": str(self.video), "current_likes": 2, "qualified_viewers": 1,
        })

    def test_rejects_unsigned_call_and_malformed_payload(self):
        self.assertEqual(self.call({"video_id": str(self.video)}, caller="content").status_code, 403)
        self.assertEqual(self.call({"video_id": str(self.video), "account_id": str(uuid4())}).status_code, 400)
        self.assertEqual(self.call({"video_id": "invalid"}).status_code, 400)
