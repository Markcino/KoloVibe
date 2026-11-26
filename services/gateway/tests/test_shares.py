import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from service.shares import video_share
from service.routes import engagement
from .test_accounts import Response

LINKS = {"origin": "https://links.example.test", "ios_app_id": "ABCDE12345.com.kolovibe.kolovibe",
         "android_package": None, "android_fingerprints": []}
NO_APP = {**LINKS, "ios_app_id": None}
UNCONFIGURED = {**NO_APP, "origin": None}


class VideoShareGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.video, self.account, self.creator = uuid4(), str(uuid4()), str(uuid4())
        self.viewer = JsonResponse({"id": self.account, "roles": ["viewer"]})
        self.public = JsonResponse({"id": str(self.video), "creator_id": self.creator})

    @override_settings(APP_LINKS=LINKS)
    def test_records_owned_intent_and_returns_only_the_app_link(self):
        with patch("service.shares.current_account", return_value=self.viewer), \
                patch("service.shares.read_public_video", return_value=self.public), \
                patch("service.shares.signed_internal_request", return_value=Response(200, json.dumps({"video_id": str(self.video), "recorded": True}).encode())) as peer:
            request = self.factory.generic("POST", "/shares")
            first, second = video_share(request, self.video), video_share(request, self.video)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.content, second.content)
            self.assertEqual(json.loads(first.content), {"video_id": str(self.video), "share_url": "https://links.example.test/open/videos/" + str(self.video)})
            self.assertIn("no-store", first["Cache-Control"])
            self.assertEqual(json.loads(peer.call_args.kwargs["payload"]), {"account_id": self.account, "video_id": str(self.video), "creator_id": self.creator})
            self.assertEqual(video_share(self.factory.post("/shares", {"account_id": str(uuid4()), "day": "2000-01-01"}, content_type="application/json"), self.video).status_code, 400)

    def test_links_no_app_can_claim_are_coded_503_and_record_nothing(self):
        with patch("service.shares.current_account", return_value=self.viewer), \
                patch("service.shares.read_public_video", return_value=self.public), \
                patch("service.shares.signed_internal_request") as peer:
            for config in (UNCONFIGURED, NO_APP):
                with self.subTest(config=config), override_settings(APP_LINKS=config):
                    result = video_share(self.factory.generic("POST", "/shares"), self.video)
                    self.assertEqual(result.status_code, 503)
                    self.assertEqual(json.loads(result.content)["code"], "share_unavailable")
            peer.assert_not_called()

    @override_settings(APP_LINKS=LINKS)
    def test_private_unapproved_or_missing_videos_get_no_link(self):
        """Content decides visibility; anything it does not return as public yields its error and no link."""
        with patch("service.shares.current_account", return_value=self.viewer), \
                patch("service.shares.read_public_video") as content, \
                patch("service.shares.signed_internal_request") as peer:
            for status in (404, 503):
                content.return_value = JsonResponse({"detail": "x"}, status=status)
                result = video_share(self.factory.generic("POST", "/shares"), self.video)
                self.assertEqual(result.status_code, status)
                self.assertNotIn(b"share_url", result.content)
            content.return_value = JsonResponse({"detail": "Not found"}, status=404)
            self.assertEqual(video_share(self.factory.generic("POST", "/shares"), self.video).status_code, 404)
            peer.assert_not_called()

    @override_settings(APP_LINKS=LINKS)
    def test_staff_roles_cannot_create_share_links(self):
        with patch("service.shares.current_account", return_value=JsonResponse({"id": self.account, "roles": ["moderator"]})), \
                patch("service.shares.read_public_video") as content:
            self.assertEqual(video_share(self.factory.generic("POST", "/shares"), self.video).status_code, 403)
            content.assert_not_called()

    @override_settings(APP_LINKS=LINKS)
    def test_auth_service_failure_and_invalid_acknowledgments_fail_closed(self):
        with patch("service.shares.signed_internal_request") as peer:
            self.assertEqual(video_share(self.factory.generic("POST", "/shares"), self.video).status_code, 401)
            peer.assert_not_called()
        with patch("service.shares.current_account", return_value=self.viewer), \
                patch("service.shares.read_public_video", return_value=self.public), \
                patch("service.shares.signed_internal_request") as peer:
            for value in (1, False):
                peer.return_value = Response(200, json.dumps({"video_id": str(self.video), "recorded": value}).encode())
                self.assertEqual(video_share(self.factory.generic("POST", "/shares"), self.video).status_code, 503)
            peer.side_effect = TimeoutError
            self.assertEqual(video_share(self.factory.generic("POST", "/shares"), self.video).status_code, 503)

    def test_share_route_uses_the_engagement_capability(self):
        with patch("service.routes.engagement.enabled", return_value=False):
            self.assertEqual(engagement.patterns(), [])
        with patch("service.routes.engagement.enabled", return_value=True):
            self.assertTrue(any(route.name == "api-video-share" for route in engagement.patterns()))
