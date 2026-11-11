import json
from urllib.error import HTTPError
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service.analytics import creator_analytics, creator_video_analytics
from .test_videos import Response


class CreatorAnalyticsGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.creator = str(uuid4())
        self.video = uuid4()

    @patch("service.analytics.signed_internal_request")
    @patch("service.analytics._owned_creator")
    def test_summary_uses_signed_owned_creator_scope(self, ownership, peer):
        ownership.return_value = (self.creator, None)
        states = {state: 0 for state in ("draft", "uploading", "processing", "failed", "review",
                                         "published", "rejected", "removed")}
        states["draft"] = 2
        peer.return_value = Response(json.dumps({"total_videos": 2, "videos_by_state": states}).encode())
        response = creator_analytics(self.factory.get("/api/v1/creators/me/analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(peer.call_args.args, ("content", "/internal/videos/analytics/summary"))
        self.assertEqual(json.loads(peer.call_args.kwargs["payload"]), {"creator_id": self.creator})

    @patch("service.analytics.signed_internal_request")
    @patch("service.analytics._owned_creator")
    def test_video_ownership_is_checked_before_engagement_query(self, ownership, peer):
        ownership.return_value = (self.creator, None)
        peer.side_effect = [
            Response(json.dumps({"video_id": str(self.video), "state": "published"}).encode()),
            Response(json.dumps({"video_id": str(self.video), "current_likes": 3,
                                 "qualified_viewers": 2}).encode()),
        ]
        response = creator_video_analytics(self.factory.get("/api/v1/creators/me/videos/id/analytics"), self.video)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["qualified_viewers"], 2)
        self.assertEqual(peer.call_args_list[0].args,
                         ("content", "/internal/videos/analytics/video"))
        self.assertEqual(json.loads(peer.call_args_list[0].kwargs["payload"]),
                         {"creator_id": self.creator, "video_id": str(self.video)})
        self.assertEqual(peer.call_args_list[1].args,
                         ("engagement", "/internal/engagement/analytics/video"))

        peer.reset_mock()
        peer.side_effect = HTTPError("http://internal", 404, "missing", {}, None)
        self.assertEqual(creator_video_analytics(
            self.factory.get("/api/v1/creators/me/videos/id/analytics"), self.video).status_code, 404)
        self.assertEqual(peer.call_count, 1)

    @patch("service.analytics.signed_internal_request")
    @patch("service.analytics._owned_creator")
    def test_auth_and_invalid_responses_fail_closed(self, ownership, peer):
        ownership.return_value = (None, JsonResponse({"detail": "Unauthorized"}, status=401))
        self.assertEqual(creator_analytics(self.factory.get("/api/v1/creators/me/analytics")).status_code, 401)
        peer.assert_not_called()
        ownership.return_value = (self.creator, None)
        self.assertEqual(creator_analytics(self.factory.get("/api/v1/creators/me/analytics?account_id=x"))
                         .status_code, 400)
        peer.assert_not_called()
        peer.return_value = Response(b'{"total_videos":true,"videos_by_state":{}}')
        self.assertEqual(creator_analytics(self.factory.get("/api/v1/creators/me/analytics")).status_code, 503)
