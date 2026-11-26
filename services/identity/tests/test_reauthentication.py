import json
import secrets
from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import accounts, preferences_privacy
from service.models import (Account, AuditDelivery, LoginSession, LoginThrottle, PrivacyRequest,
                            ReauthenticationToken, SecurityEvent)


class ReauthenticationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.password = secrets.token_urlsafe(32)
        self.account = Account.objects.create_user("viewer@example.test", self.password, "Viewer")
        self.other = Account.objects.create_user("other@example.test", self.password, "Other")
        self.sessions = [LoginSession.objects.create(
            account=owner, refresh_digest=secrets.token_hex(32),
            expires_at=timezone.now() + timedelta(days=1))
            for owner in (self.account, self.account, self.other)]
        self.tokens = [accounts._issue(session) for session in self.sessions]

    def post(self, view, data):
        return view(self.factory.post("/internal/auth/test", json.dumps(data),
                                      content_type="application/json"))

    def reauth(self, index=0, **fields):
        return self.post(accounts.reauthenticate, {
            "access_token": self.tokens[index]["access_token"],
            "current_password": self.password, **fields})

    def request_privacy(self, proof, index=0, kind="access", **fields):
        return self.post(preferences_privacy.privacy_requests, {
            "access_token": self.tokens[index]["access_token"], "operation": "create",
            "kind": kind, "reauth_token": proof, **fields})

    def test_token_is_hashed_bound_five_minutes_and_audited_via_outbox(self):
        now = timezone.now()
        with patch("django.utils.timezone.now", return_value=now):
            response = self.reauth()
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(set(data), {"reauth_token", "expires_at"})
        row = ReauthenticationToken.objects.get()
        self.assertEqual(row.digest, accounts._digest("reauth:" + data["reauth_token"]))
        self.assertNotIn(data["reauth_token"], row.digest)
        self.assertEqual(row.account_id, self.account.id)
        self.assertEqual(row.session_id, self.sessions[0].id)
        self.assertEqual(row.expires_at, now + timedelta(minutes=5))
        self.assertEqual(data["expires_at"], row.expires_at.isoformat())
        event = SecurityEvent.objects.get(kind="account.reauthenticated")
        self.assertEqual(event.actor_id, self.account.id)
        self.assertTrue(AuditDelivery.objects.filter(event=event, delivered_at__isnull=True).exists())

    def test_wrong_password_is_generic_and_attempt_budget_spans_sessions(self):
        for index in range(accounts.LOGIN_LIMIT):
            response = self.reauth(index=index % 2, current_password="incorrect-password")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.content), {"detail": "Reauthentication failed"})
        self.assertEqual(self.reauth().status_code, 429)
        self.assertFalse(ReauthenticationToken.objects.exists())
        self.assertEqual(SecurityEvent.objects.filter(kind="account.reauthentication_failed").count(), 5)
        self.assertTrue(AuditDelivery.objects.filter(event__kind="account.reauthentication_throttled").exists())
        LoginThrottle.objects.update(window_started_at=timezone.now() - accounts.LOGIN_WINDOW)
        self.assertEqual(self.reauth().status_code, 200)

    def test_successful_issuance_is_rate_limited_and_legacy_path_shares_budget(self):
        for _ in range(accounts.LOGIN_LIMIT):
            self.assertEqual(self.reauth().status_code, 200)
        self.assertEqual(self.reauth().status_code, 429)
        response = self.post(preferences_privacy.privacy_requests, {
            "access_token": self.tokens[1]["access_token"], "operation": "create",
            "kind": "deletion", "current_password": self.password})
        self.assertEqual(response.status_code, 429)
        response = self.post(accounts.change_password, {
            "access_token": self.tokens[0]["access_token"], "current_password": self.password,
            "new_password": secrets.token_urlsafe(32)})
        self.assertEqual(response.status_code, 429)
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password(self.password))

    def test_token_cannot_cross_account_or_session_or_fall_back_to_password(self):
        proof = json.loads(self.reauth().content)["reauth_token"]
        for index in (1, 2):
            response = self.request_privacy(proof, index=index, current_password=self.password)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.content), {"detail": "Reauthentication failed"})
        self.assertIsNone(ReauthenticationToken.objects.get().used_at)
        response = self.request_privacy(proof)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(json.loads(response.content)), {"id", "kind", "status", "created_at"})
        self.assertIsNotNone(ReauthenticationToken.objects.get().used_at)
        self.assertEqual(self.request_privacy(proof, kind="deletion").status_code, 400)
        self.assertEqual(PrivacyRequest.objects.count(), 1)

    def test_expiry_boundary_and_revoked_or_expired_session_reject_proof(self):
        proof = json.loads(self.reauth().content)["reauth_token"]
        expiry = ReauthenticationToken.objects.get().expires_at
        with patch("django.utils.timezone.now", return_value=expiry):
            self.assertEqual(self.request_privacy(proof).status_code, 400)
        self.assertIsNone(ReauthenticationToken.objects.get().used_at)
        LoginSession.objects.filter(pk=self.sessions[0].id).update(expires_at=timezone.now())
        self.assertEqual(self.request_privacy(proof).status_code, 401)
        self.assertEqual(self.reauth().status_code, 401)
        LoginSession.objects.filter(pk=self.sessions[0].id).update(
            expires_at=timezone.now() + timedelta(days=1), revoked_at=timezone.now())
        self.assertEqual(self.request_privacy(proof).status_code, 401)
        self.assertEqual(self.reauth().status_code, 401)

    def test_open_duplicate_is_409_consumes_proof_and_closed_request_allows_new_intake(self):
        for status in (PrivacyRequest.Status.RECEIVED, PrivacyRequest.Status.IN_REVIEW):
            PrivacyRequest.objects.all().delete()
            previous = PrivacyRequest.objects.create(account=self.account, kind="deletion", status=status)
            proof = json.loads(self.reauth().content)["reauth_token"]
            response = self.request_privacy(proof, kind="deletion")
            self.assertEqual(response.status_code, 409)
            self.assertEqual(json.loads(response.content)["code"], "request_open")
            self.assertIsNotNone(ReauthenticationToken.objects.get(digest=accounts._digest("reauth:" + proof)).used_at)
            with self.assertRaises(IntegrityError), transaction.atomic():
                PrivacyRequest.objects.create(account=self.account, kind="deletion")
            previous.status = PrivacyRequest.Status.COMPLETED
            previous.save(update_fields=["status"])
            proof = json.loads(self.reauth().content)["reauth_token"]
            self.assertEqual(self.request_privacy(proof, kind="deletion").status_code, 201)
        self.account.refresh_from_db()
        self.assertTrue(self.account.is_active)
        self.assertEqual(self.post(accounts.validate_access,
            {"access_token": self.tokens[0]["access_token"]}).status_code, 200)

    def test_list_exposes_only_canonical_statuses_and_own_receipts(self):
        # One open request per kind: "processing" is shown by moving the access request on afterwards.
        access = PrivacyRequest.objects.create(account=self.account, kind="access", status="received")
        for status in ("in_review", "completed", "declined"):
            PrivacyRequest.objects.create(account=self.account, kind="deletion", status=status,
                                          decline_code="WITHDRAWN" if status == "declined" else "")
        PrivacyRequest.objects.create(account=self.other, kind="access")

        def listed():
            response = self.post(preferences_privacy.privacy_requests, {
                "access_token": self.tokens[0]["access_token"], "operation": "list"})
            return json.loads(response.content)["items"]

        items = listed()
        self.assertEqual(len(items), 4)
        PrivacyRequest.objects.filter(pk=access.pk).update(status="processing")
        items += listed()
        self.assertEqual({item["status"] for item in items}, set(PrivacyRequest.Status.values))
        self.assertTrue(all(set(item) == {"id", "kind", "status", "created_at"} for item in items))

    def test_issuance_and_consumption_roll_back_when_audit_outbox_fails(self):
        with patch("service.accounts.record", side_effect=DatabaseError), self.assertRaises(DatabaseError):
            self.reauth()
        self.assertFalse(ReauthenticationToken.objects.exists())
        proof = json.loads(self.reauth().content)["reauth_token"]
        with patch("service.preferences_privacy.record", side_effect=DatabaseError), self.assertRaises(DatabaseError):
            self.request_privacy(proof)
        self.assertFalse(PrivacyRequest.objects.exists())
        self.assertIsNone(ReauthenticationToken.objects.get().used_at)

    def test_invalid_fields_and_missing_current_password_are_rejected(self):
        for fields in ({}, {"current_password": None}, {"current_password": ""},
                       {"current_password": "x" * 129}, {"current_password": self.password, "role": "administrator"}):
            response = self.post(accounts.reauthenticate, {
                "access_token": self.tokens[0]["access_token"], **fields})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.content), {"detail": "Reauthentication failed"})
        self.assertFalse(ReauthenticationToken.objects.exists())
