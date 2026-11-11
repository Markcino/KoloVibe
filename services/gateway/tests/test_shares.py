import importlib.util
import json
import os
import secrets
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from service import settings as gateway_settings
from service.shares import video_share
from service.routes import engagement
from .test_accounts import Response


class VideoShareGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.video, self.account, self.creator = uuid4(), str(uuid4()), str(uuid4())
        self.viewer = JsonResponse({"id": self.account, "roles": ["viewer"]})
        self.public = JsonResponse({"id": str(self.video), "creator_id": self.creator})

    @override_settings(KOLOVIBE_PUBLIC_WEB_ORIGIN="https://app.example.test")
    def test_records_owned_intent_and_builds_only_canonical_share_url(self):
        with patch("service.shares.current_account", return_value=self.viewer), \
                patch("service.shares.read_public_video", return_value=self.public), \
                patch("service.shares.signed_internal_request", return_value=Response(200, json.dumps({"video_id": str(self.video), "recorded": True}).encode())) as peer:
            request = self.factory.generic("POST", "/shares")
            first, second = video_share(request, self.video), video_share(request, self.video)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.content, second.content)
            self.assertEqual(json.loads(first.content), {"video_id": str(self.video), "share_url": "https://app.example.test/videos/" + str(self.video)})
            self.assertIn("no-store", first["Cache-Control"])
            self.assertEqual(json.loads(peer.call_args.kwargs["payload"]), {"account_id": self.account, "video_id": str(self.video), "creator_id": self.creator})
            self.assertEqual(video_share(self.factory.post("/shares", {"account_id": str(uuid4()), "day": "2000-01-01"}, content_type="application/json"), self.video).status_code, 400)

    @override_settings(KOLOVIBE_PUBLIC_WEB_ORIGIN=None)
    def test_unconfigured_origin_is_coded_503_and_nonpublic_video_is_404(self):
        with patch("service.shares.current_account", return_value=self.viewer), \
                patch("service.shares.read_public_video", return_value=self.public) as content, \
                patch("service.shares.signed_internal_request") as peer:
            result = video_share(self.factory.generic("POST", "/shares"), self.video)
            self.assertEqual(result.status_code, 503)
            self.assertEqual(json.loads(result.content)["code"], "share_unavailable")
            content.return_value = JsonResponse({"detail": "Not found"}, status=404)
            self.assertEqual(video_share(self.factory.generic("POST", "/shares"), self.video).status_code, 404)
            peer.assert_not_called()

    @override_settings(KOLOVIBE_PUBLIC_WEB_ORIGIN="https://app.example.test")
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

    def load_settings(self, value):
        spec = importlib.util.spec_from_file_location("service._share_settings_test", Path(gateway_settings.__file__))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"KOLOVIBE_ENV": "local", "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
                                    "KOLOVIBE_PUBLIC_WEB_ORIGIN": value}, clear=True):
            spec.loader.exec_module(module)
        return module

    def test_origin_is_https_only_validated_at_settings_load_and_normalized(self):
        userinfo = "user:" + secrets.token_urlsafe(12)
        self.assertEqual(self.load_settings("https://app.example.test/").KOLOVIBE_PUBLIC_WEB_ORIGIN, "https://app.example.test")
        self.assertIsNone(self.load_settings("").KOLOVIBE_PUBLIC_WEB_ORIGIN)
        for value in ("http://app.example.test", "//app.example.test", "https://app.example.test/path",
                      f"https://{userinfo}@app.example.test", "https://app.example.test?a=1",
                      "https://app.example.test/#fragment", "https://app.example.test:99999", "https://app.example.test\\evil"):
            with self.subTest(origin=value), self.assertRaises(RuntimeError):
                self.load_settings(value)

    def test_share_route_uses_the_engagement_capability(self):
        with patch("service.routes.engagement.enabled", return_value=False):
            self.assertEqual(engagement.patterns(), [])
        with patch("service.routes.engagement.enabled", return_value=True):
            self.assertTrue(any(route.name == "api-video-share" for route in engagement.patterns()))
