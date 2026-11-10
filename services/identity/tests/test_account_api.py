import json
import secrets
import smtplib
import time
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from service import accounts
from service.models import Account, EmailVerification, LoginSession, UsedRefreshToken


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EMAIL_HOST="smtp.example.test", DEFAULT_FROM_EMAIL="noreply@example.test")
class AccountApiTests(TestCase):
    def test_mail_failure_rolls_back_registration(self):
        with patch("service.accounts.send_mail", side_effect=smtplib.SMTPException), \
                self.assertLogs("service.accounts", level="ERROR"):
            response = self.post(accounts.register, {"email": "user@example.test",
                "password": self.password, "display_name": "Viewer"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Account.objects.exists())
        self.assertFalse(EmailVerification.objects.exists())

    def test_expired_verification_cannot_activate_account(self):
        self.post(accounts.register, {"email": "user@example.test",
            "password": self.password, "display_name": "Viewer"})
        EmailVerification.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        code = mail.outbox[0].body.split(": ", 1)[1]
        self.assertEqual(self.post(accounts.verify_email, {"code": code}).status_code, 400)
        self.assertFalse(Account.objects.get().is_active)

    def setUp(self):
        self.factory = RequestFactory()
        self.password = secrets.token_urlsafe(24)

    def post(self, view, body, origin="127.0.0.1"):
        request = self.factory.post("/internal/auth/test", json.dumps(body),
                                    content_type="application/json", REMOTE_ADDR=origin)
        return view(request)

    def register_and_verify(self):
        response = self.post(accounts.register, {"email": "User@Example.test",
                                                  "password": self.password,
                                                  "display_name": "Local User"})
        self.assertEqual(response.status_code, 201)
        account = Account.objects.get(email="user@example.test")
        self.assertFalse(account.is_active)
        self.assertNotIn(self.password, mail.outbox[0].body)
        code = mail.outbox[0].body.split(": ", 1)[1]
        self.assertEqual(self.post(accounts.verify_email, {"code": code}).status_code, 200)
        account.refresh_from_db()
        self.assertTrue(account.is_active)
        self.assertIsNotNone(account.email_verified_at)
        self.assertEqual(self.post(accounts.verify_email, {"code": code}).status_code, 400)
        return account

    def test_registration_verification_and_duplicate(self):
        self.register_and_verify()
        response = self.post(accounts.register, {"email": "USER@example.test",
                                                  "password": self.password,
                                                  "display_name": "Someone Else"})
        self.assertEqual(response.status_code, 409)

    def test_refresh_rotation_replay_revokes_access(self):
        self.register_and_verify()
        login = self.post(accounts.login, {"email": "user@example.test",
                                           "password": self.password})
        self.assertEqual(login.status_code, 200)
        first = json.loads(login.content)
        self.assertEqual(self.post(accounts.validate_access,
                                   {"access_token": first["access_token"]}).status_code, 200)
        rotated = self.post(accounts.refresh, {"refresh_token": first["refresh_token"]})
        self.assertEqual(rotated.status_code, 200)
        second = json.loads(rotated.content)
        self.assertNotEqual(first["refresh_token"], second["refresh_token"])
        self.assertEqual(UsedRefreshToken.objects.count(), 1)
        self.assertEqual(self.post(accounts.refresh,
                                   {"refresh_token": first["refresh_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.validate_access,
                                   {"access_token": second["access_token"]}).status_code, 401)
        self.assertIsNotNone(LoginSession.objects.get().revoked_at)

    def test_creator_verification_requires_recorded_email_verification(self):
        account = Account.objects.create_user(
            email="unverified@example.test", password=self.password, display_name="Local Viewer",
        )
        login = self.post(accounts.login, {"email": account.email, "password": self.password})
        token = json.loads(login.content)["access_token"]
        request = {"access_token": token, "include_email_verification": True}
        self.assertIs(json.loads(self.post(accounts.validate_access, request).content)["email_verified"], False)

        account.email_verified_at = timezone.now()
        account.save(update_fields=["email_verified_at"])
        self.assertIs(json.loads(self.post(accounts.validate_access, request).content)["email_verified"], True)
        ordinary = self.post(accounts.validate_access, {"access_token": token})
        self.assertNotIn("email_verified", json.loads(ordinary.content))

    def test_logout_revokes_access(self):
        self.register_and_verify()
        token = json.loads(self.post(accounts.login, {"email": "user@example.test",
                                                     "password": self.password}).content)["access_token"]
        self.assertEqual(self.post(accounts.revoke, {"access_token": token}).status_code, 204)
        self.assertEqual(self.post(accounts.validate_access,
                                   {"access_token": token}).status_code, 401)

    def test_failed_login_is_throttled(self):
        self.register_and_verify()
        incorrect = secrets.token_urlsafe(24)
        for _ in range(5):
            self.assertEqual(self.post(accounts.login, {"email": "user@example.test",
                                                       "password": incorrect}).status_code, 401)
        self.assertEqual(self.post(accounts.login, {"email": "user@example.test",
                                                   "password": self.password}).status_code, 429)

    def test_privileged_role_cannot_sign_in_without_mfa(self):
        account = self.register_and_verify()
        account.role = Account.Role.MODERATOR
        account.save(update_fields=["role"])
        self.assertEqual(self.post(accounts.login, {"email": account.email,
                                                   "password": self.password}).status_code, 403)

    def test_role_promotion_cannot_reuse_existing_unprivileged_session(self):
        account = self.register_and_verify()
        tokens = json.loads(self.post(accounts.login, {
            "email": account.email, "password": self.password}).content)
        account.role = Account.Role.MODERATOR
        account.save(update_fields=["role"])
        self.assertEqual(self.post(accounts.validate_access, {
            "access_token": tokens["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.refresh, {
            "refresh_token": tokens["refresh_token"]}).status_code, 403)

    def test_access_expiry_does_not_expire_refresh_session(self):
        account = self.register_and_verify()
        tokens = json.loads(self.post(accounts.login, {
            "email": account.email, "password": self.password}).content)
        with patch("django.core.signing.time.time", return_value=time.time() + accounts.ACCESS_SECONDS + 1):
            self.assertEqual(self.post(accounts.validate_access, {
                "access_token": tokens["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.refresh, {
            "refresh_token": tokens["refresh_token"]}).status_code, 200)

    @override_settings(EMAIL_HOST="")
    def test_registration_fails_closed_without_delivery(self):
        response = self.post(accounts.register, {"email": "user@example.test",
                                                  "password": self.password,
                                                  "display_name": "Local User"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Account.objects.exists())
