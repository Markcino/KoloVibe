import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service import account_lookup
from service.creator_onboarding import _valid_response


class AccountLookupGatewayTests(SimpleTestCase):
    def post(self, body, token="Bearer access-token-value", invoke=None):
        request = RequestFactory().post("/lookup", json.dumps(body), content_type="application/json",
                                        **({"HTTP_AUTHORIZATION": token} if token else {}))
        with patch("service.account_lookup._invoke", return_value=invoke or JsonResponse({}, status=404)) as call:
            return account_lookup.lookup(request), call

    def candidate(self, **changes):
        return {"account_id": str(uuid4()), "display_name": "Ada Eze", "role": "viewer", "email_verified": True, **changes}

    def test_requires_a_bearer_token_and_an_exact_body(self):
        response, call = self.post({"email": "a@example.test"}, token=None)
        self.assertEqual(response.status_code, 401)
        # Authority is Identity's decision and must come first (Phase 11 D11-005): a malformed body is not answered with a schema
        # error by the Gateway. Only the token is forwarded, so a caller without authority is refused by Identity whatever the body,
        # and nothing the caller chose is passed on.
        for body in ({}, {"email": "a@example.test", "role": "creator"}, [], "x"):
            response, call = self.post(body, invoke=JsonResponse({"detail": "Forbidden"}, status=403))
            self.assertEqual(response.status_code, 403, body)
            self.assertEqual(call.call_args.args[:2], ("/internal/auth/account-lookup", {"access_token": "access-token-value"}), body)
        response, _ = self.post({}, invoke=JsonResponse({"detail": "Invalid email address"}, status=400))
        self.assertEqual(response.status_code, 400, "an authorized caller still gets the validation error")

    def test_forwards_only_the_token_and_email_and_validates_the_candidate(self):
        good = self.candidate()
        response, call = self.post({"email": "a@example.test"}, invoke=JsonResponse(good))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(call.call_args.args[:2], ("/internal/auth/account-lookup",
                                                  {"access_token": "access-token-value", "email": "a@example.test"}))
        for bad in (self.candidate(role="administrator"), self.candidate(email="a@example.test"), self.candidate(email_verified="yes"),
                    self.candidate(account_id="x"), self.candidate(display_name="")):
            response, _ = self.post({"email": "a@example.test"}, invoke=JsonResponse(bad))
            self.assertEqual(response.status_code, 503, bad)
        response, _ = self.post({"email": "a@example.test"}, invoke=JsonResponse({"detail": "Account unavailable"}, status=404))
        self.assertEqual(response.status_code, 404)


class PendingApplicationContractTests(SimpleTestCase):
    def row(self, **changes):
        return {"account_id": str(uuid4()), "status": "pending", "creator_id": str(uuid4()), "handle": "ada_eze",
                "submitted_at": "2026-11-23T10:00:00+00:00", **changes}

    def test_pending_rows_need_a_valid_handle_and_timestamp(self):
        row = self.row()
        page = lambda *rows: {"items": list(rows), "next_cursor": None}
        self.assertTrue(_valid_response("pending", page(row), None))
        for bad in (self.row(handle="Bad Handle"), self.row(handle="ab"), self.row(submitted_at="2026-11-23T10:00:00"),
                    self.row(submitted_at=None), self.row(status="approved"), {**row, "email": "a@example.test"},
                    {k: v for k, v in row.items() if k != "handle"}):
            self.assertFalse(_valid_response("pending", page(bad), None), bad)
