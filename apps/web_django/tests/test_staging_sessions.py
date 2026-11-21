"""Staging BFF boundary: only an opaque browser cookie, encrypted server state."""

import secrets
import uuid
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from web.models import WebCredential


@override_settings(
    ENVIRONMENT="staging", WEB_TOKEN_KEY=Fernet.generate_key(),
    SESSION_COOKIE_NAME="__Host-kolovibe_session", SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
)
class StagingSessions(TestCase):
    def setUp(self):
        self.sid = uuid.uuid4()
        self.access = secrets.token_urlsafe(36)
        self.refresh = str(self.sid) + "." + secrets.token_urlsafe(48)

    def account(self):
        return {"id": str(self.sid), "email": "administrator@example.test",
                "display_name": "Administrator", "roles": ["administrator"]}

    def login(self):
        with patch("web.views._api", return_value=(202, {
                "mfa_required": True, "challenge_token": secrets.token_urlsafe(48), "expires_in": 300})):
            self.client.post(reverse("login"), {"email": self.account()["email"], "password": secrets.token_urlsafe(30)})
        with patch("web.views._api", return_value=(200, {
                "access_token": self.access, "refresh_token": self.refresh, "user": self.account()})):
            return self.client.post(reverse("login-mfa"), {"code": "012345"})

    def test_login_cookie_is_opaque_and_credentials_encrypted_in_database(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertIn("__Host-kolovibe_session", response.cookies)
        cookie = response.cookies["__Host-kolovibe_session"]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/")
        self.assertEqual(cookie["domain"], "")
        self.assertNotIn(self.access, cookie.value)
        self.assertNotIn(self.refresh, cookie.value)
        row = WebCredential.objects.get()
        self.assertEqual(row.identity_session_id, self.sid)
        self.assertNotIn(self.refresh.encode(), bytes(row.ciphertext))
        self.assertNotIn(self.access.encode(), bytes(row.ciphertext))

    def test_static_assets_are_served_from_the_web_image(self):
        response = self.client.get("/static/css/site.css")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/css; charset=utf-8")
        self.assertTrue(b"body" in b"".join(response.streaming_content))
        self.assertEqual(self.client.get("/static/unknown.txt").status_code, 404)

    def test_authenticated_request_checks_identity_and_revocation(self):
        self.login()
        account = self.account()
        with patch("web.views._api", return_value=(200, account)) as api:
            self.assertContains(self.client.get(reverse("account")), "Administrator")
        self.assertEqual(api.call_args.args, ("/me",))
        with patch("web.views._api", side_effect=[(401, {}), (401, {})]):
            response = self.client.get(reverse("account"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(WebCredential.objects.exists())
        self.assertEqual(response.cookies["__Host-kolovibe_session"]["max-age"], 0)

    def test_refresh_rotates_only_encrypted_server_record(self):
        self.login()
        rotated = {"access_token": secrets.token_urlsafe(36),
                   "refresh_token": str(self.sid) + "." + secrets.token_urlsafe(48)}
        account = self.account()
        with patch("web.views._api", side_effect=[(401, {}), (200, rotated), (200, account)]) as api:
            self.assertEqual(self.client.get(reverse("account")).status_code, 200)
        self.assertEqual(api.call_count, 3)
        self.assertNotIn(rotated["refresh_token"].encode(), bytes(WebCredential.objects.get().ciphertext))
        self.assertNotIn(rotated["refresh_token"], self.client.cookies["__Host-kolovibe_session"].value)

    def test_idle_and_absolute_deadlines_reject_browser_session(self):
        for field, age in (("last_activity_at", timedelta(minutes=30)),
                           ("created_at", timedelta(hours=8))):
            with self.subTest(field=field):
                self.login()
                row = WebCredential.objects.get()
                if field == "created_at":
                    row.absolute_expires_at = timezone.now() - timedelta(seconds=1)
                    row.save(update_fields=["absolute_expires_at"])
                else:
                    row.last_activity_at = timezone.now() - age - timedelta(seconds=1)
                    row.save(update_fields=["last_activity_at"])
                with patch("web.views._api") as api:
                    response = self.client.get(reverse("account"))
                self.assertEqual(response.status_code, 302)
                self.assertFalse(WebCredential.objects.exists())
                api.assert_not_called()

    def test_logout_outage_revokes_browser_state_and_reports_failure(self):
        self.login()
        with patch("web.views._api", return_value=(503, {})) as api:
            response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "could not be confirmed", status_code=503)
        self.assertEqual(api.call_args.kwargs["data"], {"refresh_token": self.refresh})
        self.assertFalse(WebCredential.objects.exists())
        self.assertEqual(response.cookies["__Host-kolovibe_session"]["max-age"], 0)

    def test_privileged_login_and_role_elevation_do_not_keep_web_session(self):
        for role in ("moderator", "administrator"):
            with self.subTest(role=role), patch("web.views._api", return_value=(200, {
                "access_token": self.access, "refresh_token": self.refresh,
                "user": {"roles": [role]},
            })):
                response = self.client.post(reverse("login"), {
                    "email": "privileged@example.test", "password": secrets.token_urlsafe(30),
                })
            self.assertEqual(response.status_code, 403)
            self.assertFalse(WebCredential.objects.exists())
            self.assertFalse(self.client.session.get("authenticated"))

        self.login()
        account = {"id": str(self.sid), "roles": ["viewer"]}
        with patch("web.views._api", return_value=(200, account)):
            response = self.client.get(reverse("account"))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(WebCredential.objects.exists())
        self.assertEqual(response.cookies["__Host-kolovibe_session"]["max-age"], 0)
