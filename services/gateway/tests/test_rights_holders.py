"""Decision E (D11-008): the Gateway boundary for verified rights holders and reviewer copyright signals."""

import json
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase

from service.reviewer_contracts import valid_copyright_context
from service.rights_holders import rights_holders, valid_row
from .test_accounts import Response

EVIDENCE = "Signed letter from the label confirming authority"


class RightsHolderGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin, self.account = str(uuid4()), str(uuid4())
        self.row = {"account_id": self.account, "organisation": "Monrovia Records", "evidence": EVIDENCE,
                    "verified_by": self.admin, "verified_at": "2026-11-25T12:00:00+00:00", "revoked_at": None,
                    "active": True}

    def run_as(self, request, operation, role="administrator", mfa=True, answer=None, target_id=None):
        with patch("service.rights_holders.authenticated_actor", return_value=(self.admin, role)), \
                patch("service.standing.identity_context", return_value={"account_id": self.admin, "mfa_verified": mfa}), \
                patch("service.rights_holders.signed_internal_request", return_value=answer) as call:
            return rights_holders(request, operation, target_id), call

    def verify_request(self, **extra):
        return self.factory.post("/rights-holders", {"account_id": self.account, "organisation": "Monrovia Records",
                                                     "evidence": EVIDENCE} | extra, content_type="application/json")

    def test_verify_needs_an_mfa_administrator(self):
        answer = Response(201, json.dumps(self.row).encode())
        response, call = self.run_as(self.verify_request(), "rights-holders", answer=answer)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(call.call_args.args[1], "/internal/moderation/rights-holder-verify")
        sent = json.loads(call.call_args.kwargs["payload"])
        self.assertEqual((sent["mfa_verified"], sent["data"]["account_id"]), (True, self.account))
        for role, mfa in (("moderator", True), ("administrator", False), ("creator", True)):
            response, call = self.run_as(self.verify_request(), "rights-holders", role=role, mfa=mfa, answer=answer)
            self.assertEqual(response.status_code, 403)
            call.assert_not_called()
        response, call = self.run_as(self.verify_request(extra=1), "rights-holders", answer=answer)
        self.assertEqual(response.status_code, 400)
        call.assert_not_called()

    def test_answers_are_checked(self):
        for wrong in ({"account_id": str(uuid4())}, {"active": False}, {"verified_by": self.account}, {"note": 1}):
            answer = Response(201, json.dumps(self.row | wrong).encode())
            self.assertEqual(self.run_as(self.verify_request(), "rights-holders", answer=answer)[0].status_code, 503)
        revoked = self.row | {"active": False, "revoked_at": "2026-11-25T13:00:00+00:00"}
        response, call = self.run_as(self.factory.generic("POST", "/revoke"), "rights-holder-revoke",
                                     answer=Response(200, json.dumps(revoked).encode()), target_id=self.account)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(call.call_args.kwargs["payload"])["data"], {"account_id": self.account})
        page = Response(200, json.dumps({"items": [self.row], "next_cursor": None}).encode())
        self.assertEqual(self.run_as(self.factory.get("/rights-holders"), "rights-holders", answer=page)[0].status_code, 200)
        bad = Response(200, json.dumps({"items": [self.row], "next_cursor": str(uuid4())}).encode())
        self.assertEqual(self.run_as(self.factory.get("/rights-holders"), "rights-holders", answer=bad)[0].status_code, 503)
        self.assertFalse(valid_row(self.row | {"evidence": "short"}))

    def test_reviewer_copyright_context(self):
        context = {"work_reference": "Original recording", "claimant_verified": True, "organisation": "Label",
                   "claimant_claims": 2, "claimant_dismissed": 1, "creator_active_strikes": 0}
        self.assertTrue(valid_copyright_context(None))
        self.assertTrue(valid_copyright_context(context))
        for wrong in ({"claimant_verified": False}, {"claimant_dismissed": 3}, {"claimant_claims": None},
                      {"creator_active_strikes": -1}, {"claimant_id": str(uuid4())}):
            self.assertFalse(valid_copyright_context(context | wrong), wrong)
