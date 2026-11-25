"""Decision F (D-8): the Gateway boundary for creator measures, appeals and publish enforcement."""

from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service import media
from service.creator_restrictions import _valid, creator_restrictions, valid_restriction
from service.routes import creator_studio
from .test_accounts import Response

KEY = "restriction-key-0001"


class CreatorRestrictionGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin, self.account, self.creator, self.restriction = (str(uuid4()) for _ in range(4))
        self.public = {"id": self.restriction, "kind": "upload", "reason_code": "SPAM_REPEAT",
                       "policy_version": "creator-enforcement-v1", "issued_at": "2026-11-25T12:00:00+00:00",
                       "expires_at": None, "lifted_at": None, "active": True, "appeal": None}
        self.private = self.public | {"creator_id": self.creator, "reason": "Repeated spam uploads after a warning",
                                      "issued_by": self.admin, "lifted_by": None, "lift_reason": ""}

    def run_as(self, request, operation, role="administrator", mfa=True, answer=None, target_id=None, actor=None):
        actor = actor or (self.admin if role == "administrator" else self.account)
        with patch("service.creator_restrictions.authenticated_actor", return_value=(actor, role)), \
                patch("service.standing.identity_context", return_value={"account_id": actor, "mfa_verified": mfa}), \
                patch("service.creator_restrictions.signed_internal_request", return_value=answer) as call:
            return creator_restrictions(request, operation, target_id), call

    def issue_request(self, key=KEY, **body):
        body = {"kind": "upload", "reason_code": "SPAM_REPEAT", "policy_version": "creator-enforcement-v1",
                "reason": "Repeated spam uploads after a warning", "expires_at": None} | body
        return self.factory.post("/restrictions", body, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key)

    def test_issue_needs_an_mfa_verified_administrator_and_a_key(self):
        answer = Response(201, json.dumps(self.private).encode())
        response, call = self.run_as(self.issue_request(), "admin_restrictions", answer=answer, target_id=self.creator)
        self.assertEqual(response.status_code, 201)
        sent = json.loads(call.call_args.kwargs["payload"])
        self.assertEqual(call.call_args.args[1], "/internal/creators/restrictions/issue")
        self.assertEqual((sent["actor_id"], sent["role"], sent["data"]["creator_id"], sent["data"]["key"]),
                         (self.admin, "administrator", self.creator, KEY))
        for role, mfa in (("administrator", False), ("moderator", True), ("creator", True)):
            with self.subTest(role=role, mfa=mfa):
                response, call = self.run_as(self.issue_request(), "admin_restrictions", role=role, mfa=mfa,
                                             answer=answer, target_id=self.creator)
                self.assertEqual(response.status_code, 403)
                call.assert_not_called()
        for request in (self.issue_request(key="short"), self.issue_request(extra=1)):
            response, call = self.run_as(request, "admin_restrictions", answer=answer, target_id=self.creator)
            self.assertEqual(response.status_code, 400)
            call.assert_not_called()

    def test_answers_that_do_not_match_the_request_are_refused(self):
        for wrong in ({"creator_id": str(uuid4())}, {"kind": "suspension"}, {"active": True, "lifted_at": "2026-11-25T13:00:00+00:00"},
                      {"secret": 1}):
            with self.subTest(wrong=wrong):
                answer = Response(201, json.dumps(self.private | wrong).encode())
                response, _ = self.run_as(self.issue_request(), "admin_restrictions", answer=answer, target_id=self.creator)
                self.assertEqual(response.status_code, 503)

    def test_creator_sees_only_public_fields(self):
        answer = Response(200, json.dumps({"creator_id": self.creator, "items": [self.public]}).encode())
        response, call = self.run_as(self.factory.get("/mine"), "mine", role="creator", answer=answer)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(call.call_args.kwargs["payload"])["data"], {})
        leaked = Response(200, json.dumps({"creator_id": self.creator, "items": [self.private]}).encode())
        self.assertEqual(self.run_as(self.factory.get("/mine"), "mine", role="creator", answer=leaked)[0].status_code, 503)
        self.assertEqual(self.run_as(self.factory.get("/mine"), "mine", role="moderator", answer=answer)[0].status_code, 403)
        self.assertEqual(self.run_as(self.factory.post("/mine"), "mine", role="creator", answer=answer)[0].status_code, 405)

    def test_appeal_and_service_refusals_pass_through_with_their_detail(self):
        request = self.factory.post("/appeals", {"reason": "These were my own original videos"},
                                    content_type="application/json")
        answer = Response(201, json.dumps({"id": str(uuid4()), "status": "open"}).encode())
        response, call = self.run_as(request, "appeal", role="creator", answer=answer, target_id=self.restriction)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(call.call_args.kwargs["payload"])["data"],
                         {"restriction_id": self.restriction, "reason": "These were my own original videos"})
        with patch("service.creator_restrictions.authenticated_actor", return_value=(self.account, "creator")), \
                patch("service.creator_restrictions.signed_internal_request",
                      side_effect=HTTPError("https://creators.invalid", 409, "", {}, BytesIO(b'{"detail":"Already appealed"}'))):
            response = creator_restrictions(request, "appeal", self.restriction)
        self.assertEqual((response.status_code, json.loads(response.content)["detail"]), (409, "Already appealed"))

    def test_appeal_queue_cursor_and_decision_checks(self):
        appeal = {"id": str(uuid4()), "status": "open", "created_at": "2026-11-25T12:30:00+00:00",
                  "reason": "Please look again", "restriction": self.private, "decided_at": None, "decision_reason": ""}
        answer = Response(200, json.dumps({"items": [appeal], "next_cursor": appeal["id"]}).encode())
        self.assertEqual(self.run_as(self.factory.get("/appeals"), "appeals", answer=answer)[0].status_code, 200)
        self.assertEqual(self.run_as(self.factory.get("/appeals", {"cursor": "x"}), "appeals", answer=answer)[0].status_code, 400)
        bad = Response(200, json.dumps({"items": [appeal], "next_cursor": str(uuid4())}).encode())
        self.assertEqual(self.run_as(self.factory.get("/appeals"), "appeals", answer=bad)[0].status_code, 503)
        decided = appeal | {"status": "lifted", "decided_at": "2026-11-25T13:00:00+00:00", "decision_reason": "Evidence"}
        self.assertTrue(_valid("decide", decided, {"appeal_id": appeal["id"]}))
        self.assertFalse(_valid("decide", appeal, {"appeal_id": appeal["id"]}))
        self.assertFalse(_valid("decide", decided | {"decided_at": None}, {"appeal_id": appeal["id"]}))

    def test_validators_reject_inconsistent_rows(self):
        self.assertTrue(valid_restriction(self.public, private=False))
        self.assertFalse(valid_restriction(self.private, private=False))
        self.assertFalse(valid_restriction(self.private | {"lifted_at": "2026-11-25T13:00:00+00:00", "active": False}, private=True))
        self.assertFalse(valid_restriction(self.public | {"issued_at": "2026-11-25T12:00:00"}, private=False))
        self.assertFalse(_valid("capabilities", {"creator_id": None, "upload": True, "publish": False, "monetization": False}, {}))
        self.assertTrue(_valid("capabilities", {"creator_id": None, "upload": False, "publish": False, "monetization": False}, {}))

    def test_publish_follows_the_publish_capability_only(self):
        def publish(caps):
            with patch("service.media._owned_creator", return_value=(self.creator, None)), \
                    patch("service.media.authenticated_actor", return_value=(self.account, "creator")), \
                    patch("service.media.restriction_capabilities", return_value=JsonResponse(caps)), \
                    patch("service.media.forward_media", return_value=JsonResponse({}, status=200)) as call:
                return media.video_visibility(self.factory.generic("POST", "/publish"), str(uuid4()), "publish").status_code, call
        allowed = {"creator_id": self.creator, "upload": False, "publish": True, "monetization": False}
        status, call = publish(allowed)  # an upload-only measure does not block publishing
        self.assertEqual(status, 200)
        call.assert_called_once()
        for caps in (allowed | {"publish": False}, allowed | {"creator_id": str(uuid4())}):
            status, call = publish(caps)
            self.assertEqual(status, 403)
            call.assert_not_called()

    def test_routes_are_media_gated(self):
        with patch("service.routes.creator_studio.enabled", side_effect=lambda name: name == "media"):
            names = {route.name for route in creator_studio.patterns()}
        self.assertTrue({"api-own-restrictions", "api-own-restriction-appeal", "api-admin-creator-restrictions",
                         "api-admin-restriction-lift", "api-admin-restriction-appeals",
                         "api-admin-restriction-appeal-decision"} <= names)
