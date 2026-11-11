import io
import json
from urllib.error import HTTPError
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service.moderation import moderation_endpoint
from service.pilot_points import creator_points
from service.routes import moderation as moderation_routes, points as points_routes
from service.standing import identity_context, standing
from .test_videos import Response


class PointsCompletionGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account, self.creator, self.ident = (str(uuid4()) for _ in range(3))
        self.actor = self.enterContext(patch("service.pilot_points.authenticated_actor", return_value=(self.account, "creator")))
        self.enterContext(patch("service.pilot_points.creator_ownership", return_value=JsonResponse({"creator_id": self.creator})))
        self.peer = self.enterContext(patch("service.pilot_points.signed_internal_request"))
        self.entry = {"id": self.ident, "creator_id": self.creator, "amount": 1, "kind": "award",
                      "rule_version": "DEC-003-v1", "created_at": "2026-11-11T12:00:00Z", "status": "pending", "video_id": None}

    def test_filters_and_detail_use_authenticated_owner_and_validate_echo(self):
        self.peer.return_value = Response(json.dumps({"items": [self.entry], "next_cursor": None}).encode())
        result = creator_points(self.factory.get("/points/entries?status=pending"), "entries")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json.loads(self.peer.call_args.kwargs["payload"]),
                         {"account_id": self.account, "creator_id": self.creator, "status": "pending", "cursor": None})
        self.peer.return_value = Response(json.dumps(self.entry).encode())
        self.assertEqual(creator_points(self.factory.get("/points/entries/id"), "entry", self.ident).status_code, 200)
        self.peer.return_value = Response(json.dumps(self.entry | {"id": str(uuid4())}).encode())
        self.assertEqual(creator_points(self.factory.get("/points/entries/id"), "entry", self.ident).status_code, 503)

    def test_bad_filters_duplicate_parameters_and_foreign_results_fail_closed(self):
        for query in ("status=withheld", "status=all&status=pending", "cursor=bad", "account_id=foreign"):
            self.assertEqual(creator_points(self.factory.get("/entries?" + query), "entries").status_code, 400)
        self.peer.assert_not_called()
        for entry in (self.entry | {"creator_id": str(uuid4())}, self.entry | {"amount": True},
                      self.entry | {"status": "confirmed"}, self.entry | {"video_id": "bad"}):
            self.peer.return_value = Response(json.dumps({"items": [entry], "next_cursor": None}).encode())
            self.assertEqual(creator_points(self.factory.get("/entries?status=pending"), "entries").status_code, 503)

    def test_all_points_routes_reject_client_awards_and_adjustments(self):
        with patch("service.routes.points.enabled", side_effect=lambda capability: capability == "points"):
            patterns = points_routes.patterns()
        self.assertEqual(len(patterns), 3)
        for pattern in patterns:
            for method in ("post", "put", "patch", "delete"):
                request = getattr(self.factory, method)("/points", {"amount": 1000}, content_type="application/json")
                kwargs = dict(pattern.default_args)
                if kwargs["operation"] == "entry": kwargs["entry_id"] = self.ident
                self.assertEqual(pattern.callback(request, **kwargs).status_code, 405)
        self.actor.assert_not_called()
        self.peer.assert_not_called()


class ModerationCompletionGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account, self.creator, self.video = (str(uuid4()) for _ in range(3))
        self.actor = self.enterContext(patch("service.moderation.authenticated_actor", return_value=(self.account, "creator")))
        self.peer = self.enterContext(patch("service.moderation.signed_internal_request"))
        self.notice = {"video_id": self.video, "decision": "removed", "reason_code": "POLICY_HARMFUL",
                       "decided_at": "2026-11-11T12:00:00Z", "appealable": True, "appeal": None}

    def test_reviewer_role_and_live_mfa_required_for_all_queues_and_decisions(self):
        for operation in ("review_queue", "reports", "appeals", "video_decision", "report_decision", "appeal_decision"):
            request = self.factory.get("/queue") if "decision" not in operation else self.factory.post("/decision", {
                 "action": "remove", "reason": "Reviewed harmful content"}, content_type="application/json")
            self.actor.return_value = (self.account, "creator")
            self.assertEqual(moderation_endpoint(request, operation, self.video).status_code, 403)
            self.actor.return_value = (self.account, "moderator")
            with patch("service.standing.identity_context", return_value={"account_id": self.account, "account_status": "active", "email_verified": True, "mfa_verified": False}):
                self.assertEqual(moderation_endpoint(request, operation, self.video).status_code, 403)
        self.peer.assert_not_called()

    def test_verified_reviewer_context_is_bound_to_actor_and_signed_envelope(self):
        self.actor.return_value = (self.account, "moderator")
        self.peer.return_value = Response(b'{"items":[],"next_cursor":null}')
        with patch("service.standing.identity_context", return_value={"account_id": self.account, "account_status": "active", "email_verified": True, "mfa_verified": True}) as context:
            response = moderation_endpoint(self.factory.get("/queue"), "reports")
            self.assertEqual(response.status_code, 200)
            self.assertIs(json.loads(self.peer.call_args.kwargs["payload"])["mfa_verified"], True)
            context.return_value["account_id"] = str(uuid4())
            self.assertEqual(moderation_endpoint(self.factory.get("/queue"), "reports").status_code, 403)

    def test_duplicate_report_code_survives_gateway(self):
        raw = b'{"detail":"An open report already exists","code":"already_reported"}'
        self.peer.side_effect = HTTPError("https://moderation.test/internal", 409, "Conflict", {}, io.BytesIO(raw))
        request = self.factory.post("/reports", {"video_id": self.video, "reason": "spam"},
                   content_type="application/json", HTTP_IDEMPOTENCY_KEY="completion-report-001")
        response = moderation_endpoint(request, "report")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content)["code"], "already_reported")

    def test_notice_uses_owner_lookup_and_rejects_mismatched_video_or_malformed_decision(self):
        with patch("service.moderation.creator_ownership", return_value=JsonResponse({"creator_id": self.creator})) as owner:
            self.peer.return_value = Response(json.dumps(self.notice).encode())
            response = moderation_endpoint(self.factory.get("/notice"), "notice", self.video)
            self.assertEqual(response.status_code, 200)
            owner.assert_called_with(self.account, "creator")
            payload = json.loads(self.peer.call_args.kwargs["payload"])
            self.assertEqual(payload["data"], {"video_id": self.video, "creator_id": self.creator})
            for notice in (self.notice | {"video_id": str(uuid4())}, self.notice | {"appealable": 1},
                           self.notice | {"decision": "made_up"}, self.notice | {"reason_code": "bad code"}):
                self.peer.return_value = Response(json.dumps(notice).encode())
                self.assertEqual(moderation_endpoint(self.factory.get("/notice"), "notice", self.video).status_code, 503)

    def test_standing_and_notice_routes_are_moderation_gated(self):
        with patch("service.routes.moderation.enabled", return_value=False):
            self.assertEqual(moderation_routes.patterns(), [])
        with patch("service.routes.moderation.enabled", return_value=True):
            names = {pattern.name for pattern in moderation_routes.patterns()}
            self.assertTrue({"own-standing", "own-video-notice"} <= names)


class StandingGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account, self.creator = str(uuid4()), str(uuid4())
        self.enterContext(patch("service.standing.authenticated_actor", return_value=(self.account, "creator")))
        self.context = self.enterContext(patch("service.standing.identity_context", return_value={
             "account_id": self.account, "account_status": "active", "email_verified": True, "mfa_verified": False}))
        self.peer = self.enterContext(patch("service.standing.signed_internal_request"))

    def test_restricted_creator_standing_composes_real_status_without_public_profile_read(self):
        self.peer.return_value = Response(json.dumps({"creator_id": self.creator, "creator_status": "restricted", "publishing_allowed": False}).encode())
        with patch("service.moderation._forward", return_value=JsonResponse({"notices": []})) as moderation:
            response = standing(self.factory.get("/me/standing"))
        self.assertEqual(json.loads(response.content), {"account_status": "active", "creator_status": "restricted", "publishing_allowed": False, "notices": []})
        self.assertEqual(moderation.call_args.args, ("standing", self.account, "creator", {"creator_id": self.creator}))
        self.assertIn("no-store", response["Cache-Control"])

    def test_standing_rejects_scope_overrides_and_invalid_peer_state(self):
        self.assertEqual(standing(self.factory.get("/standing?account_id=other")).status_code, 400)
        self.peer.assert_not_called()
        self.peer.return_value = Response(json.dumps({"creator_id": self.creator, "creator_status": "suspended", "publishing_allowed": True}).encode())
        self.assertEqual(standing(self.factory.get("/standing")).status_code, 503)
        self.peer.side_effect = OSError
        self.assertEqual(standing(self.factory.get("/standing")).status_code, 503)

    def test_active_creator_publishing_requires_live_verified_email(self):
        self.peer.return_value = Response(json.dumps({"creator_id": self.creator, "creator_status": "active", "publishing_allowed": True}).encode())
        with patch("service.moderation._forward", return_value=JsonResponse({"notices": []})):
            self.assertTrue(json.loads(standing(self.factory.get("/standing")).content)["publishing_allowed"])
            self.context.return_value["email_verified"] = False
            self.assertFalse(json.loads(standing(self.factory.get("/standing")).content)["publishing_allowed"])

    def test_identity_context_is_strict_and_never_trusts_client_mfa_claims(self):
        # Direct reference is the real imported function, independent of module patch.
        request = self.factory.get("/standing", HTTP_AUTHORIZATION="Bearer signed-token")
        with patch("service.standing._invoke", return_value=JsonResponse({"account_id": self.account, "account_status": "active", "email_verified": True, "mfa_verified": 1})) as peer:
            self.assertEqual(identity_context(request).status_code, 503)
            self.assertEqual(peer.call_args.args[1], {"access_token": "signed-token"})
