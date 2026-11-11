import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service.pilot_points import creator_points, watch
from .test_videos import Response


class PilotGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account, self.creator, self.creator_account = (str(uuid4()) for _ in range(3))
        self.video, self.session = uuid4(), str(uuid4())
        self.expires = "2026-11-10T20:00:00+00:00"
        self.actor = self.enterContext(patch("service.pilot_points.authenticated_actor",
                                            return_value=(self.account, "viewer")))
        self.peer = self.enterContext(patch("service.pilot_points.signed_internal_request"))

    def as_peer(self, data):
        self.peer.return_value = Response(json.dumps(data).encode())

    def test_watch_rejects_client_qualification_points_and_server_metadata_before_forwarding(self):
        base = {"video_id": str(self.video), "session_id": self.session, "position_ms": 2000}
        with patch("service.media.forward_media") as content:
            for field, value in (("qualified", True), ("points", 100), ("creator_user_id", self.creator_account),
                                 ("duration_ms", 1), ("revision", 0), ("qualified_at", self.expires)):
                response = watch(self.factory.post("/watch", base | {field: value}, content_type="application/json"))
                self.assertEqual(response.status_code, 400)
            content.assert_not_called()
            self.peer.assert_not_called()

    @patch("service.pilot_points.read_creator")
    @patch("service.media.forward_media")
    def test_watch_uses_signed_account_and_metadata(self, media, owner):
        media.return_value = JsonResponse({"creator_id": self.creator, "duration_ms": 2130,
                                           "revision": 1, "playback_url": "private-url",
                                           "expires_at": self.expires})
        owner.return_value = JsonResponse({"user_id": self.creator_account})
        self.as_peer({"session_id": self.session, "expires_at": self.expires})
        response = watch(self.factory.post("/watch", b"", content_type="application/json"), self.video)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {
            "session_id": self.session, "session_expires_at": self.expires,
            "playback_url": "private-url", "playback_expires_at": self.expires,
        })
        self.assertEqual(self.peer.call_args.args, ("engagement", "/internal/engagement/watch/start"))
        self.assertEqual(json.loads(self.peer.call_args.kwargs["payload"]), {
            "account_id": self.account, "video_id": str(self.video), "creator_user_id": self.creator_account,
            "duration_ms": 2130, "revision": 1,
        })
        self.peer.reset_mock()
        self.actor.return_value = (self.creator_account, "viewer")
        self.assertEqual(watch(self.factory.post("/watch", b"", content_type="application/json"), self.video).status_code, 403)
        self.peer.assert_not_called()

    @patch("service.pilot_points.creator_ownership")
    def test_points_rejects_foreign_creator_and_client_account_override(self, ownership):
        ownership.return_value = JsonResponse({"creator_id": self.creator, "upload_eligible": True})
        expected = {"creator_id": self.creator, "balance": 5, "currency": "POINTS", "as_of": self.expires}
        self.as_peer(expected)
        request = self.factory.get("/points")
        self.assertEqual(json.loads(creator_points(request, "balance").content), expected)
        self.assertEqual(json.loads(self.peer.call_args.kwargs["payload"]), {
            "account_id": self.account, "creator_id": self.creator,
        })
        self.as_peer(expected | {"creator_id": str(uuid4())})
        self.assertEqual(creator_points(request, "balance").status_code, 503)
        self.peer.reset_mock()
        self.assertEqual(creator_points(self.factory.get("/points?account_id=foreign"), "balance").status_code, 400)
        self.peer.assert_not_called()
