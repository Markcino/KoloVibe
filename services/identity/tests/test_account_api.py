import json
import secrets

from django.core import mail
from django.test import RequestFactory, TestCase, override_settings

from service import accounts
from service.models import Account, LoginSession, UsedRefreshToken


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EMAIL_HOST="smtp.example.test", DEFAULT_FROM_EMAIL="noreply@example.test")
class AccountApiTests(TestCase):
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

    @override_settings(EMAIL_HOST="")
    def test_registration_fails_closed_without_delivery(self):
        response = self.post(accounts.register, {"email": "user@example.test",
                                                  "password": self.password,
                                                  "display_name": "Local User"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Account.objects.exists())
