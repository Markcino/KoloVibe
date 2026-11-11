from datetime import date, timedelta
import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service.analytics import VIDEO_STATES, creator_analytics, creator_video_analytics
from service.routes import creator_studio
from .video_fixtures import metadata


class RangeAnalyticsGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.creator, self.owner, self.video = (str(uuid4()) for _ in range(3))
        self.enterContext(patch("service.analytics._owned_creator", return_value=(self.creator, None)))
        self.enterContext(patch("service.analytics.current_account", return_value=JsonResponse({"id": self.owner})))
        self.state = {"total_videos": 1, "videos_by_state": {name: int(name == "published") for name in VIDEO_STATES}}
        self.detail = {"id": self.video, "creator_id": self.creator, "title": "Owned title", "description": "",
                       "state": "published", "created_at": "2026-11-01T12:00:00Z", "revision": 2,
                       **metadata("private"), "published_at": "2026-11-01T12:00:00Z"}

    def summary(self, period="7d"):
        days = 7 if period == "7d" else 28
        start = date(2026, 11, 11) - timedelta(days=days-1)
        return {"creator_id": self.creator, "creator_user_id": self.owner, "range": period, "qualified_plays": 2,
                "watch_time_seconds": 5.0, "likes": 1, "new_followers": 3, "shares": 4,
                "daily": [{"date": (start+timedelta(days=i)).isoformat(), "qualified_plays": 2 if i == 0 else 0,
                           "likes": 1 if i == 0 else 0} for i in range(days)],
                "top_videos": [{"video_id": self.video, "qualified_plays": 2}]}

    def test_creator_range_uses_signed_owner_and_existing_content_title_endpoint(self):
        for period in ("7d", "28d"):
            def peer(service, path, payload):
                if service == "engagement":
                    self.assertEqual(payload, {"creator_id": self.creator, "creator_user_id": self.owner, "range": period})
                    return self.summary(period)
                if path.endswith("/summary"):
                    return self.state
                self.assertEqual(path, "/internal/videos/media/detail")
                self.assertEqual(payload, {"creator_id": self.creator, "video_id": self.video})
                return self.detail
            with patch("service.analytics._peer", side_effect=peer):
                response = creator_analytics(self.factory.get("/analytics", {"range": period}))
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertEqual(data["total_videos"], 1)
            self.assertEqual(data["range"], period)
            self.assertEqual(data["top_videos"], [{"video_id": self.video, "title": "Owned title", "qualified_plays": 2}])
            self.assertNotIn("creator_user_id", data)

    def test_deleted_or_unowned_top_video_does_not_expose_identifier_or_title(self):
        with patch("service.analytics._peer", side_effect=[self.state, self.summary(), None]):
            response = creator_analytics(self.factory.get("/analytics"))
        self.assertEqual(json.loads(response.content)["top_videos"], [])
        with patch("service.analytics._peer", side_effect=[self.state, self.summary(), self.detail | {"creator_id": str(uuid4())}]):
            self.assertEqual(creator_analytics(self.factory.get("/analytics")).status_code, 503)

    def test_bad_ranges_duplicate_queries_and_actor_overrides_are_rejected(self):
        with patch("service.analytics._peer") as peer:
            for query in ({"range": "since_published"}, {"range": "90d"}, {"creator_user_id": self.owner}, {"account_id": self.owner}):
                self.assertEqual(creator_analytics(self.factory.get("/analytics", query)).status_code, 400)
            self.assertEqual(creator_analytics(self.factory.get("/analytics?range=7d&range=28d")).status_code, 400)
            self.assertEqual(creator_video_analytics(self.factory.get("/analytics", {"range": "28d"}), self.video).status_code, 400)
            peer.assert_not_called()

    def test_invalid_totals_or_daily_series_fail_closed(self):
        for fields in ({"qualified_plays": True}, {"watch_time_seconds": float("nan")}, {"watch_time_seconds": 10 ** 1000}, {"daily": []},
                       {"likes": 4}, {"creator_user_id": str(uuid4())}, {"top_videos": [{"video_id": self.video, "qualified_plays": 3}]}):
            with patch("service.analytics._peer", side_effect=[self.state, self.summary() | fields]):
                self.assertEqual(creator_analytics(self.factory.get("/analytics")).status_code, 503)

    def test_video_since_published_requires_content_ownership_and_trusted_publication_time(self):
        counts = {"video_id": self.video, "current_likes": 4, "qualified_viewers": 1, "range": "since_published",
                  "qualified_plays": 2, "watch_time_seconds": 5.0, "likes": 3, "shares": 1, "average_watch_seconds": 2.5}
        with patch("service.analytics._peer", side_effect=[{"video_id": self.video, "state": "published"}, self.detail, counts]) as peer:
            response = creator_video_analytics(self.factory.get("/analytics", {"range": "since_published"}), self.video)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["average_watch_seconds"], 2.5)
        self.assertEqual(peer.call_args.args, ("engagement", "/internal/engagement/analytics/video", {
            "video_id": self.video, "range": "since_published", "published_at": self.detail["published_at"]}))
        with patch("service.analytics._peer", return_value=None) as peer:
            self.assertEqual(creator_video_analytics(self.factory.get("/analytics"), self.video).status_code, 404)
            self.assertEqual(peer.call_count, 1)

    def test_analytics_routes_are_independent_of_media_capability(self):
        with patch("service.routes.creator_studio.enabled", side_effect=lambda name: name == "analytics"):
            self.assertEqual({route.name for route in creator_studio.patterns()}, {"api-creator-analytics", "api-creator-video-analytics"})
