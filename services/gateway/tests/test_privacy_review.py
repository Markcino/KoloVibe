"""Decision C: the Gateway boundary for privacy request review and account holds."""

import io
import json
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase

from service import privacy_review as review
from .test_accounts import Response


class PrivacyReviewGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.target, self.account = str(uuid4()), str(uuid4())
        self.row = {"id": self.target, "account_id": self.account, "kind": "deletion", "status": "in_review",
                    "created_at": "2026-11-26T10:00:00+00:00", "review_started_at": "2026-11-26T11:00:00+00:00",
                    "decided_at": None, "decline_code": None, "held": False, "erasure": []}
        self.hold = {"id": str(uuid4()), "account_id": self.account, "reason_code": "LEGAL_CLAIM",
                     "note": "Open dispute", "placed_by": str(uuid4()), "placed_at": "2026-11-26T11:00:00Z",
                     "released_at": None}

    def send(self, view, request, answer, *args, **kwargs):
        request.META["HTTP_AUTHORIZATION"] = "Bearer access-token"
        with patch("service.accounts.signed_internal_request", return_value=answer) as call:
            return view(request, *args, **kwargs), call

    def sent(self, call):
        self.assertEqual(call.call_args.args[1], "/internal/auth/privacy-review")
        return json.loads(call.call_args.kwargs["payload"])

    def test_list_forwards_only_known_filters(self):
        page = {"items": [self.row], "next_cursor": None}
        response, call = self.send(review.collection, self.factory.get("/x", {"status": "in_review"}),
                                   Response(200, json.dumps(page).encode()))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.sent(call), {"access_token": "access-token", "operation": "list",
                                           "status": "in_review"})
        for query in ({"status": "deleted"}, {"cursor": "nope"}, {"other": "1"}):
            response, call = self.send(review.collection, self.factory.get("/x", query), None)
            self.assertEqual(response.status_code, 400)
            call.assert_not_called()

    def test_no_token_never_reaches_identity(self):
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(review.collection(self.factory.get("/x")).status_code, 401)
        call.assert_not_called()

    def test_steps_carry_only_their_fields(self):
        declined = self.row | {"status": "declined", "decline_code": "WITHDRAWN", "decided_at": "2026-11-26T12:00:00Z"}
        request = self.factory.post("/x", {"decline_code": "WITHDRAWN"}, content_type="application/json")
        response, call = self.send(review.step, request, Response(200, json.dumps(declined).encode()),
                                   operation="decline", target_id=self.target)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.sent(call)["operation"], "decline")
        for operation, body in (("decline", {"decline_code": "BECAUSE"}), ("decline", {}),
                                ("review", {"decline_code": "WITHDRAWN"}), ("approve-deletion", {"x": 1})):
            request = self.factory.post("/x", body, content_type="application/json")
            response, call = self.send(review.step, request, None, operation=operation, target_id=self.target)
            self.assertEqual(response.status_code, 400, (operation, body))
            call.assert_not_called()
        processing = self.row | {"status": "processing", "decided_at": "2026-11-26T12:00:00Z"}
        request = self.factory.generic("POST", "/x")
        response, call = self.send(review.step, request, Response(200, json.dumps(processing).encode()),
                                   operation="approve-deletion", target_id=self.target)
        self.assertEqual((response.status_code, self.sent(call)["operation"]), (200, "approve-deletion"))

    def test_answers_are_checked(self):
        for wrong in ({"status": "erased"}, {"decline_code": "WITHDRAWN"}, {"held": "no"},
                      {"created_at": "2026-11-26T10:00:00"}, {"extra": 1}, {"erasure": None},
                      {"erasure": [{"service": "finance", "confirmed": True, "retained": []}]},
                      {"erasure": [{"service": "content", "confirmed": "yes", "retained": []}]},
                      {"erasure": [{"service": "content", "confirmed": True, "retained": ["Person Name"]}]},
                      {"erasure": [{"service": "content", "confirmed": True, "retained": [], "counts": {}}]},
                      {"erasure": [{"service": "content", "confirmed": False, "retained": []}] * 2}):
            request = self.factory.generic("POST", "/x")
            response, _ = self.send(review.step, request, Response(200, json.dumps(self.row | wrong).encode()),
                                    operation="review", target_id=self.target)
            self.assertEqual(response.status_code, 503, wrong)
        response, _ = self.send(review.holds, self.factory.get("/x"),
                                Response(200, json.dumps({"items": [self.hold | {"reason_code": "X"}]}).encode()),
                                target_id=self.account)
        self.assertEqual(response.status_code, 503)

    def test_erasure_progress_passes_through(self):
        row = self.row | {"status": "processing", "erasure": [
            {"service": "creators", "confirmed": True, "retained": ["measures"]},
            {"service": "content", "confirmed": False, "retained": []}]}
        response, _ = self.send(review.step, self.factory.generic("POST", "/x"), Response(200, json.dumps(row).encode()),
                                operation="review", target_id=self.target)
        self.assertEqual((response.status_code, json.loads(response.content)), (200, row))

    def test_a_conflict_code_from_identity_reaches_the_console(self):
        error = HTTPError("http://identity", 409, "Conflict", {}, io.BytesIO(json.dumps(
            {"detail": "This account is on hold", "code": "account_on_hold"}).encode()))
        request = self.factory.generic("POST", "/x")
        request.META["HTTP_AUTHORIZATION"] = "Bearer access-token"
        with patch("service.accounts.signed_internal_request", side_effect=error):
            response = review.step(request, operation="approve-deletion", target_id=self.target)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content)["code"], "account_on_hold")

    def test_holds_place_and_release(self):
        request = self.factory.post("/x", {"reason_code": "LEGAL_CLAIM", "note": "Open dispute"},
                                    content_type="application/json")
        response, call = self.send(review.holds, request, Response(201, json.dumps(self.hold).encode()),
                                   target_id=self.account)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.sent(call)["account_id"], self.account)
        for body in ({"reason_code": "BECAUSE", "note": "Open dispute"}, {"reason_code": "LEGAL_CLAIM", "note": "x"},
                     {"reason_code": "LEGAL_CLAIM"}):
            request = self.factory.post("/x", body, content_type="application/json")
            response, call = self.send(review.holds, request, None, target_id=self.account)
            self.assertEqual(response.status_code, 400, body)
            call.assert_not_called()
        released = self.hold | {"released_at": "2026-11-26T13:00:00Z"}
        response, call = self.send(review.release, self.factory.generic("POST", "/x"),
                                   Response(200, json.dumps(released).encode()), target_id=self.hold["id"])
        self.assertEqual((response.status_code, self.sent(call)["operation"]), (200, "hold-release"))
