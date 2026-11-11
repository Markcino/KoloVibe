from datetime import timedelta
import json
import secrets
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from service.accounts import _issue, standing_context
from service.models import Account, LoginSession, TotpFactor


class StandingContextTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create_user("standing@example.test", secrets.token_urlsafe(32), "Standing")
        self.session = LoginSession.objects.create(account=self.account, authenticated_role="viewer",
                      refresh_digest="test-only", expires_at=timezone.now() + timedelta(minutes=10))
        self.token = _issue(self.session)["access_token"]

    def call(self, caller="gateway", **extra):
        request = RequestFactory().post("/internal/auth/standing", {"access_token": self.token, **extra}, content_type="application/json")
        request.service_caller = caller
        return standing_context(request)

    def test_minimal_live_context_has_no_personal_profile_and_rejects_revocation(self):
        self.assertEqual(json.loads(self.call().content), {"account_id": str(self.account.id), "account_status": "active", "mfa_verified": False, "email_verified": False})
        self.session.revoked_at = timezone.now()
        self.session.save(update_fields=["revoked_at"])
        self.assertEqual(self.call().status_code, 401)

    @override_settings(STAGING_PRIVILEGED=True)
    def test_reviewer_context_rejects_password_only_session_then_accepts_live_mfa(self):
        self.account.role = "moderator"
        self.account.save(update_fields=["role"])
        self.session.authenticated_role = "moderator"
        self.session.save(update_fields=["authenticated_role"])
        self.assertEqual(self.call().status_code, 401)
        TotpFactor.objects.create(account=self.account, encrypted_secret="unused-in-session-read")
        self.session.mfa_verified_at = timezone.now()
        self.session.save(update_fields=["mfa_verified_at"])
        self.assertIs(json.loads(self.call().content)["mfa_verified"], True)
        self.session.mfa_verified_at = timezone.now() - timedelta(minutes=16)
        self.session.save(update_fields=["mfa_verified_at"])
        self.assertEqual(self.call().status_code, 401)

    def test_gateway_only_and_client_state_overrides_rejected(self):
        self.assertEqual(self.call(caller="moderation").status_code, 403)
        self.assertEqual(self.call(mfa_verified=True).status_code, 401)
