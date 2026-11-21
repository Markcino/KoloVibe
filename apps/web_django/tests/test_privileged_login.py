import json
import secrets
import uuid
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from web import staging_session
from web.models import WebCredential


@override_settings(
    ENVIRONMENT="staging", WEB_TOKEN_KEY=Fernet.generate_key(),
    SESSION_COOKIE_NAME="__Host-kolovibe_session", SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
)
class PrivilegedWebLoginTests(TestCase):
    def setUp(self):
        self.email = "administrator@example.test"
        self.challenge = secrets.token_urlsafe(48)
        self.access = secrets.token_urlsafe(48)
        self.refresh = str(uuid.uuid4()) + "." + secrets.token_urlsafe(48)
        self.account = {"id": str(uuid.uuid4()), "email": self.email,
                        "display_name": "Administrator", "roles": ["administrator"]}

    def begin(self, client=None, **payload):
        with patch("web.views._api", return_value=(202, {
                "mfa_required": True, "challenge_token": self.challenge, "expires_in": 300, **payload})):
            return (client or self.client).post(reverse("login"), {
                "email": self.email, "password": secrets.token_urlsafe(30),
            })

    def tokens(self, **payload):
        return {"access_token": self.access, "refresh_token": self.refresh,
                "user": self.account, **payload}

    def finish(self, **payload):
        with patch("web.views._api", return_value=(200, self.tokens(**payload))) as api:
            response = self.client.post(reverse("login-mfa"), {"code": "012345"})
        return response, api

    def test_password_stage_is_not_authenticated_and_challenge_is_server_encrypted(self):
        response = self.begin()
        self.assertRedirects(response, reverse("login-mfa"), fetch_redirect_response=False)
        self.assertFalse(WebCredential.objects.exists())
        state = self.client.session
        self.assertFalse(state.get("authenticated"))
        self.assertNotIn(self.challenge, json.dumps(dict(state)))
        page = self.client.get(reverse("login-mfa"))
        self.assertContains(page, "authenticator")
        for secret in (self.challenge, self.access, self.refresh):
            self.assertNotIn(secret.encode(), page.content)
            self.assertNotIn(secret, self.client.cookies["__Host-kolovibe_session"].value)

    def test_mfa_success_uses_existing_factor_api_and_caps_browser_lifetime(self):
        self.begin()
        self.client.get(reverse("login-mfa"))
        old_csrf = self.client.cookies["csrftoken"].value
        old_session_key = self.client.session.session_key
        response, api = self.finish()
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(api.call_args.args, ("/auth/mfa/verify",))
        self.assertEqual(api.call_args.kwargs["data"], {
            "challenge_token": self.challenge, "code": "012345"})
        row = WebCredential.objects.get()
        self.assertNotEqual(row.session_key, old_session_key)
        self.assertEqual(row.absolute_expires_at - row.created_at, timedelta(minutes=15))
        self.assertEqual(self.client.session.get("authenticated_role"), "administrator")
        self.assertNotIn(staging_session.MFA_PENDING, self.client.session)
        for secret in (self.access, self.refresh):
            self.assertNotIn(secret.encode(), bytes(row.ciphertext))
            self.assertNotIn(secret, response.cookies["__Host-kolovibe_session"].value)
        self.assertNotIn("kv_access", response.cookies)
        self.assertNotIn("kv_refresh", response.cookies)
        self.assertNotEqual(self.client.cookies["csrftoken"].value, old_csrf)
        with patch("web.views._api", return_value=(200, self.account)):
            self.assertContains(self.client.get(reverse("account")), "Administrator")

    def test_moderator_also_requires_the_mfa_flow(self):
        self.account["roles"] = ["moderator"]
        self.begin()
        self.assertEqual(self.finish()[0].status_code, 302)
        self.assertEqual(self.client.session.get("authenticated_role"), "moderator")

    def test_missing_expired_or_malformed_challenge_does_not_call_verifier(self):
        with patch("web.views._api") as api:
            self.assertEqual(self.client.post(reverse("login-mfa"), {
                "challenge_token": self.challenge, "code": "012345"}).status_code, 302)
            api.assert_not_called()
        self.begin()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(seconds=301)), \
                patch("web.views._api") as api:
            self.assertEqual(self.client.post(reverse("login-mfa"), {"code": "012345"}).status_code, 302)
            api.assert_not_called()
        for invalid in ({"expires_in": 3600}, {"expires_in": True}, {"challenge_token": "short"},
                        {"mfa_required": False}):
            self.begin()
            self.assertEqual(self.begin(**invalid).status_code, 503)
            self.assertNotIn(staging_session.MFA_PENDING, self.client.session)
        self.assertFalse(WebCredential.objects.exists())

    def test_wrong_code_can_retry_but_throttle_and_outage_never_authenticate(self):
        self.begin()
        for status in (401, 503):
            with patch("web.views._api", return_value=(status, {})):
                self.assertEqual(self.client.post(reverse("login-mfa"), {"code": "012345"}).status_code, status)
            self.assertFalse(WebCredential.objects.exists())
            self.assertIn(staging_session.MFA_PENDING, self.client.session)
        with patch("web.views._api", return_value=(429, {})):
            self.assertEqual(self.client.post(reverse("login-mfa"), {"code": "012345"}).status_code, 429)
        self.assertNotIn(staging_session.MFA_PENDING, self.client.session)
        self.assertFalse(WebCredential.objects.exists())

    def test_account_or_role_mismatch_discards_challenge_and_revokes_issued_session(self):
        for changes in ({"email": "someone-else@example.test"}, {"roles": ["viewer"]}):
            self.begin()
            with patch("web.views._api", side_effect=[
                    (200, self.tokens(user={**self.account, **changes})), (204, {})]) as api:
                response = self.client.post(reverse("login-mfa"), {"code": "012345"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(api.call_args.args, ("/auth/logout",))
            self.assertEqual(api.call_args.kwargs["data"], {"refresh_token": self.refresh})
            self.assertNotIn(staging_session.MFA_PENDING, self.client.session)
            self.assertFalse(WebCredential.objects.exists())

    def test_role_change_and_absolute_expiry_clear_privileged_browser_state(self):
        self.begin()
        self.finish()
        with patch("web.views._api", return_value=(200, {**self.account, "roles": ["viewer"]})):
            self.assertEqual(self.client.get(reverse("account")).status_code, 403)
        self.assertFalse(WebCredential.objects.exists())
        self.begin()
        self.finish()
        WebCredential.objects.update(absolute_expires_at=timezone.now() - timedelta(seconds=1))
        with patch("web.views._api") as api:
            self.assertEqual(self.client.get(reverse("account")).status_code, 302)
            api.assert_not_called()
        self.assertFalse(WebCredential.objects.exists())

    def test_csrf_protects_mfa_submission(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("login"), secure=True)
        with patch("web.views._api", return_value=(202, {
                "mfa_required": True, "challenge_token": self.challenge, "expires_in": 300})):
            response = client.post(reverse("login"), {
                "email": self.email, "password": secrets.token_urlsafe(30),
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            }, secure=True, HTTP_REFERER="https://testserver/login/")
        self.assertEqual(response.status_code, 302)
        with patch("web.views._api") as api:
            response = client.post(reverse("login-mfa"), {"code": "012345"}, secure=True)
            self.assertEqual(response.status_code, 403)
            api.assert_not_called()
        self.assertFalse(WebCredential.objects.exists())

    def test_backend_rejection_clears_privileged_session(self):
        for replies in ([(403, {})], [(401, {}), (403, {})]):
            self.begin()
            self.finish()
            with patch("web.views._api", side_effect=replies):
                self.assertRedirects(self.client.get(reverse("account")), "/login/?expired=1",
                                     fetch_redirect_response=False)
            self.assertFalse(WebCredential.objects.exists())
            self.assertFalse(self.client.session.get("authenticated"))

    def test_recovery_code_is_forwarded_only_to_existing_mfa_verifier(self):
        self.begin()
        recovery = secrets.token_urlsafe(32)
        with patch("web.views._api", return_value=(200, self.tokens())) as api:
            response = self.client.post(reverse("login-mfa"), {"code": recovery})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(api.call_args.kwargs["data"]["code"], recovery)
        self.assertNotIn(recovery, json.dumps(dict(self.client.session)))
        self.assertNotIn(recovery.encode(), bytes(WebCredential.objects.get().ciphertext))
