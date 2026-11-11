import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service.moderation import moderation_endpoint
from .test_videos import Response


class ModerationGatewayTests(SimpleTestCase):
    @patch("service.moderation.signed_internal_request")
    def test_anonymous_requests_do_not_reach_moderation(self, peer):
        request = RequestFactory().get("/moderation/reports")
        self.assertEqual(moderation_endpoint(request, "reports").status_code, 401)
        peer.assert_not_called()

    @patch("service.moderation.signed_internal_request")
    @patch("service.moderation.creator_ownership")
    @patch("service.moderation.authenticated_actor")
    def test_appeal_uses_creator_identity_from_signed_ownership_lookup(self, actor, ownership, peer):
        account, creator, video = (str(uuid4()) for _ in range(3))
        actor.return_value = (account, "viewer")
        ownership.return_value = JsonResponse({"creator_id": creator})
        peer.return_value = Response(json.dumps({
            "id": str(uuid4()), "video_id": video, "status": "open", "created_at": "2026-11-10T20:00:00Z",
        }).encode())
        request = RequestFactory().post("/appeal", {"reason": "Rights evidence supplied."},
                                        content_type="application/json")
        response = moderation_endpoint(request, "appeal", target_id=video)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        ownership.assert_called_once_with(account, "viewer")
        self.assertEqual(json.loads(peer.call_args.kwargs["payload"]), {
            "actor_id": account, "role": "viewer",
            "data": {"reason": "Rights evidence supplied.", "video_id": video, "creator_id": creator},
        })

    @patch("service.moderation.signed_internal_request")
    @patch("service.moderation.authenticated_actor")
    def test_own_status_reads_forward_only_authenticated_account(self, actor, peer):
        account, record, video = (str(uuid4()) for _ in range(3))
        actor.return_value = (account, "viewer")
        item = {"id": record, "video_id": video, "status": "open", "created_at": "2026-11-10T20:00:00Z",
                "reason": "spam", "details": "Private report details"}
        peer.return_value = Response(json.dumps({"items": [item], "next_cursor": None}).encode())
        request = RequestFactory().get("/api/v1/me/reports", {"cursor": str(uuid4())})
        response = moderation_endpoint(request, "own_reports")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["items"], [item])
        envelope = json.loads(peer.call_args.kwargs["payload"])
        self.assertEqual(envelope["actor_id"], account)
        self.assertEqual(envelope["role"], "viewer")
        self.assertEqual(set(envelope["data"]), {"cursor"})
        self.assertEqual(peer.call_args.args[0], "moderation")
        self.assertEqual(peer.call_args.args[1], "/internal/moderation/own_reports")

        peer.return_value = Response(json.dumps(item).encode())
        detail = moderation_endpoint(RequestFactory().get(f"/api/v1/me/reports/{record}"),
                                     "own_report", target_id=record)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(json.loads(peer.call_args.kwargs["payload"])["data"], {"target_id": record})

    @patch("service.moderation.signed_internal_request")
    @patch("service.moderation.authenticated_actor")
    def test_own_status_reads_reject_client_scoping_and_bad_cursor(self, actor, peer):
        actor.return_value = (str(uuid4()), "viewer")
        self.assertEqual(moderation_endpoint(RequestFactory().get("/me/reports", {"account_id": str(uuid4())}),
                                             "own_reports").status_code, 400)
        self.assertEqual(moderation_endpoint(RequestFactory().get("/me/appeals", {"cursor": "bad"}),
                                             "own_appeals").status_code, 400)
        self.assertEqual(moderation_endpoint(RequestFactory().get("/me/reports/id", {"account_id": str(uuid4())}),
                                             "own_report", target_id=str(uuid4())).status_code, 400)
        peer.assert_not_called()
