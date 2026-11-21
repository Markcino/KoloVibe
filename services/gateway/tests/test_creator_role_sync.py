import json
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase

from service import creator_onboarding as onboarding, creators
from .test_creators import Response


class CreatorRoleSyncTests(SimpleTestCase):
    def setUp(self):
        self.account, self.creator, self.reviewer = str(uuid4()), str(uuid4()), str(uuid4())
        self.factory = RequestFactory()
        self.eligible = {"upload_eligible": True, "creator_id": self.creator}
        self.synced = {"account_id": self.account, "role": "creator", "changed": True}

    def reply(self, data):
        return Response(json.dumps(data).encode())

    @patch("service.creator_onboarding.signed_internal_request")
    def test_review_confirms_target_eligibility_before_identity_grant_and_retries(self, call):
        application = {"account_id": self.account, "status": "approved", "creator_id": self.creator}
        request = self.factory.post("/review", {"decision": "approved"}, content_type="application/json")
        with patch.object(onboarding, "authenticated_actor", return_value=(self.reviewer, "moderator")):
            call.side_effect = [self.reply(application), self.reply(self.eligible), OSError("unavailable")]
            self.assertEqual(onboarding.creator_onboarding(request, "review", self.account).status_code, 503)
            call.side_effect = [self.reply(application), self.reply(self.eligible), self.reply(self.synced)]
            result = onboarding.creator_onboarding(request, "review", self.account)
        self.assertEqual(json.loads(result.content), application)
        eligibility_call, grant_call = call.call_args_list[-2:]
        self.assertEqual(json.loads(eligibility_call.kwargs["payload"]),
                         {"actor_id": self.account, "role": "viewer", "data": {}})
        self.assertEqual(grant_call.args, ("identity", "/internal/auth/creator-role"))
        self.assertEqual(json.loads(grant_call.kwargs["payload"]), {"account_id": self.account, **self.eligible})

    @patch("service.creator_onboarding.signed_internal_request")
    def test_existing_approved_viewer_reconciles_then_requires_sign_in(self, call):
        with patch.object(onboarding, "authenticated_actor", return_value=(self.account, "viewer")):
            call.side_effect = [self.reply(self.eligible), self.reply(self.eligible), self.reply(self.synced)]
            self.assertEqual(onboarding.creator_eligibility(self.factory.get("/eligibility")).status_code, 401)
        # Direct Studio reads also repair old accounts, while PATCH stays role-gated.
        with patch.object(creators, "authenticated_actor", return_value=(self.account, "viewer")):
            call.side_effect = [self.reply(self.eligible), self.reply(self.synced | {"changed": False})]
            self.assertEqual(creators.own_creator(self.factory.get("/api/v1/creators/me")).status_code, 401)

    @patch("service.creator_onboarding.signed_internal_request")
    def test_ineligible_mismatched_and_malformed_evidence_never_grants_role(self, call):
        for evidence in ({"upload_eligible": False, "creator_id": None},
                         {"upload_eligible": True, "creator_id": str(uuid4())},
                         {"upload_eligible": True, "creator_id": self.creator, "role": "creator"}):
            call.reset_mock()
            call.side_effect = None
            call.return_value = self.reply(evidence)
            result = onboarding.synchronize_creator_role(self.account, expected_creator_id=self.creator)
            self.assertIn(result.status_code, (403, 503))
            self.assertEqual(call.call_count, 1)
        call.return_value = self.reply({"upload_eligible": False, "creator_id": None})
        with patch.object(onboarding, "authenticated_actor", return_value=(self.account, "viewer")):
            result = onboarding.creator_eligibility(self.factory.get("/eligibility"))
            self.assertEqual(result.status_code, 200)
            self.assertFalse(json.loads(result.content)["upload_eligible"])
        with patch.object(creators, "authenticated_actor", return_value=(self.account, "viewer")):
            self.assertEqual(creators.own_creator(self.factory.get("/api/v1/creators/me")).status_code, 403)

    def test_staging_transition_requires_accounts_and_post(self):
        from pathlib import Path
        import sys
        with patch.object(sys, "path", [str(Path(__file__).resolve().parents[2]), *sys.path]):
            from staging_runtime.middleware import route_allowed
        for accounts, enabled, method, expected in ((True, True, "POST", True),
                (False, True, "POST", False), (True, False, "POST", True), (True, True, "GET", False)):
            self.assertEqual(route_allowed("identity", method, "/internal/auth/creator-role",
                accounts=accounts, onboarding=enabled), expected)
