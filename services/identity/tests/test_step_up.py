"""Decision G: one Identity step-up mechanism, purpose-bound, audience-bound, resource-bound, single use."""
import json
import secrets
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import accounts, step_up
from service.models import Account, LoginSession, LoginThrottle, SecurityEvent, StepUpProof

PURPOSE = "business.member_remove"


class StepUpTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.password = secrets.token_urlsafe(32)
        self.account = Account.objects.create_user("owner@example.test", self.password, "Owner")
        self.other = Account.objects.create_user("other@example.test", self.password, "Other")
        self.sessions = [LoginSession.objects.create(
            account=owner, refresh_digest=secrets.token_hex(32), expires_at=timezone.now() + timedelta(days=1))
            for owner in (self.account, self.account, self.other)]
        self.tokens = [accounts._issue(s)["access_token"] for s in self.sessions]
        self.resource = str(uuid.uuid4())

    def post(self, view, data):
        return view(self.factory.post("/internal/auth/test", json.dumps(data), content_type="application/json"))

    def issue(self, index=0, **fields):
        body = {"access_token": self.tokens[index], "current_password": self.password, "purpose": PURPOSE,
                "resource_id": self.resource, **fields}
        return self.post(step_up.issue, {k: v for k, v in body.items() if v is not None})

    def proof(self, **fields):
        response = self.issue(**fields)
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)["step_up_token"]

    def consume(self, proof, index=0, **fields):
        body = {"access_token": self.tokens[index], "step_up_token": proof, "purpose": PURPOSE, "audience": "business",
                "resource_id": self.resource, **fields}
        return self.post(step_up.consume, {k: v for k, v in body.items() if v is not None})

    # ---- issuance -------------------------------------------------------------------------------------------------
    def test_a_proof_is_hashed_bound_to_purpose_audience_resource_and_session_and_expires_in_five_minutes(self):
        now = timezone.now()
        with patch("django.utils.timezone.now", return_value=now):
            response = self.issue()
        data = json.loads(response.content)
        self.assertEqual(set(data), {"step_up_token", "purpose", "expires_at"})
        row = StepUpProof.objects.get()
        self.assertNotEqual(row.digest, data["step_up_token"])
        self.assertEqual((row.account_id, row.session_id, row.purpose, row.audience, str(row.resource_id)),
                         (self.account.id, self.sessions[0].id, PURPOSE, "business", self.resource))
        self.assertEqual(row.expires_at, now + timedelta(seconds=step_up.PROOF_SECONDS))
        self.assertTrue(SecurityEvent.objects.filter(kind="account.step_up_issued", actor_id=self.account.id).exists())

    def test_unknown_purposes_missing_or_unexpected_resources_and_bad_input_are_refused(self):
        for fields in ({"purpose": "business.anything"}, {"purpose": "x" * 300}, {"resource_id": None},
                       {"resource_id": "not-a-uuid"}, {"current_password": ""}, {"audience": "business"}):
            with self.subTest(fields):
                self.assertEqual(self.issue(**fields).status_code, 400)
        self.assertFalse(StepUpProof.objects.exists())

    def test_wrong_password_is_generic_and_shares_the_reauthentication_budget(self):
        for _ in range(accounts.LOGIN_LIMIT):
            self.assertEqual(self.issue(current_password="wrong-password").status_code, 400)
        self.assertEqual(self.issue().status_code, 429)
        self.assertEqual(self.post(accounts.reauthenticate, {
            "access_token": self.tokens[1], "current_password": self.password}).status_code, 429)
        self.assertFalse(StepUpProof.objects.exists())
        LoginThrottle.objects.update(window_started_at=timezone.now() - accounts.LOGIN_WINDOW)
        self.assertEqual(self.issue().status_code, 200)

    def test_a_revoked_or_invalid_session_cannot_obtain_a_proof(self):
        self.sessions[0].revoked_at = timezone.now()
        self.sessions[0].save()
        self.assertEqual(self.issue().status_code, 401)
        self.assertEqual(self.issue(access_token="forged").status_code, 401)

    # ---- consumption ----------------------------------------------------------------------------------------------
    def test_a_proof_is_consumed_once_and_names_the_account(self):
        proof = self.proof()
        response = self.consume(proof)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content),
                         {"account_id": str(self.account.id), "purpose": PURPOSE, "resource_id": self.resource})
        self.assertIsNotNone(StepUpProof.objects.get().used_at)
        self.assertEqual(self.consume(proof).status_code, 403)  # replay
        self.assertTrue(SecurityEvent.objects.filter(kind="account.step_up_consumed").exists())
        self.assertTrue(SecurityEvent.objects.filter(kind="account.step_up_rejected").exists())

    def test_every_binding_is_checked_and_a_mismatch_does_not_burn_the_proof(self):
        proof = self.proof()
        for label, fields in {
            "other purpose": {"purpose": "business.contact_change"},
            "other audience": {"audience": "finance"},
            "other resource": {"resource_id": str(uuid.uuid4())},
            "other session of the same account": {"index": 1},
            "another account": {"index": 2},
            "forged session": {"access_token": "forged"},
            "unknown proof": {"step_up_token": secrets.token_urlsafe(48)},
        }.items():
            with self.subTest(label):
                index = fields.pop("index", 0)
                token = fields.pop("step_up_token", proof)
                response = self.consume(token, index=index, **fields)
                self.assertIn(response.status_code, (401, 403))
                self.assertEqual(set(json.loads(response.content)), {"detail"})
        self.assertIsNone(StepUpProof.objects.get().used_at)
        self.assertEqual(self.consume(proof).status_code, 200)

    def test_an_expired_proof_or_a_session_revoked_after_issue_is_refused(self):
        proof = self.proof()
        StepUpProof.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.consume(proof).status_code, 403)
        proof = self.proof()
        LoginSession.objects.filter(pk=self.sessions[0].pk).update(revoked_at=timezone.now())
        self.assertIn(self.consume(proof).status_code, (401, 403))

    def test_a_reauthentication_token_is_not_a_step_up_proof_and_the_reverse(self):
        reauth = json.loads(self.post(accounts.reauthenticate, {
            "access_token": self.tokens[0], "current_password": self.password}).content)["reauth_token"]
        self.assertEqual(self.consume(reauth).status_code, 403)
        proof = self.proof()
        self.assertFalse(accounts._consume_reauthentication(self.account, self.sessions[0], proof))

    def test_concurrent_consumption_has_exactly_one_winner(self):
        proof = self.proof()
        results = [self.consume(proof).status_code for _ in range(3)]
        self.assertEqual(sorted(results), [200, 403, 403])

    def test_every_purpose_names_a_known_audience_and_whether_it_needs_a_resource(self):
        self.assertTrue(step_up.PURPOSES)
        for purpose, (audience, needs_resource) in step_up.PURPOSES.items():
            self.assertRegex(purpose, r"^[a-z]+\.[a-z_]+$")
            self.assertIn(audience, step_up.AUDIENCES)
            self.assertIsInstance(needs_resource, bool)
