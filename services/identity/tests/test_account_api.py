import json
import re
import secrets
import smtplib
import time
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from service import accounts
from service.models import (Account, AuditDelivery, EmailVerification, LoginSession, PasswordReset,
                            ReauthenticationToken, SecurityEvent, UsedRefreshToken)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EMAIL_HOST="smtp.example.test", DEFAULT_FROM_EMAIL="noreply@example.test")
class AccountApiTests(TestCase):
    def test_reset_replaces_code_and_revokes_existing_sessions(self):
        account = self.register_and_verify()
        login = self.post(accounts.login, {"email": account.email, "password": self.password})
        session = json.loads(login.content)
        second = json.loads(self.post(accounts.login,
            {"email": account.email, "password": self.password}).content)
        proof = json.loads(self.post(accounts.reauthenticate, {
            "access_token": session["access_token"], "current_password": self.password}).content)["reauth_token"]
        self.assertEqual(self.post(accounts.request_password_reset,
                                   {"email": "missing@example.test"}).status_code, 204)
        self.assertEqual(self.post(accounts.request_password_reset,
                                   {"email": account.email}).status_code, 204)
        code = self.code_from(mail.outbox[-1])
        self.assertEqual(self.post(accounts.request_password_reset,
                                   {"email": account.email}).status_code, 204)
        self.assertEqual(PasswordReset.objects.filter(account=account).count(), 1)
        other_password = secrets.token_urlsafe(28)
        self.assertEqual(self.post(accounts.reset_password,
            {"email": account.email, "code": code, "new_password": other_password}).status_code, 204)
        self.assertEqual(self.post(accounts.reset_password,
            {"email": account.email, "code": code, "new_password": secrets.token_urlsafe(28)}).status_code, 400)
        self.assertEqual(self.post(accounts.validate_access,
            {"access_token": session["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.refresh,
            {"refresh_token": session["refresh_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.validate_access,
            {"access_token": second["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.refresh,
            {"refresh_token": second["refresh_token"]}).status_code, 401)
        self.assertFalse(ReauthenticationToken.objects.filter(
            digest=accounts._digest("reauth:" + proof), used_at__isnull=True).exists())
        self.assertTrue(AuditDelivery.objects.filter(event__kind="account.password_reset").exists())
        self.assertEqual(self.post(accounts.login,
            {"email": account.email, "password": self.password}).status_code, 401)
        self.assertEqual(self.post(accounts.login,
            {"email": account.email, "password": other_password}).status_code, 200)

    def test_expired_reset_and_wrong_current_password_cannot_change_account(self):
        account = self.register_and_verify()
        session = json.loads(self.post(accounts.login,
            {"email": account.email, "password": self.password}).content)
        self.post(accounts.request_password_reset, {"email": account.email})
        code = self.code_from(mail.outbox[-1])
        PasswordReset.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.post(accounts.reset_password,
            {"email": account.email, "code": code, "new_password": secrets.token_urlsafe(28)}).status_code, 400)
        self.assertEqual(self.post(accounts.change_password, {
            "access_token": session["access_token"],
            "current_password": secrets.token_urlsafe(28),
            "new_password": secrets.token_urlsafe(28),
        }).status_code, 400)
        self.assertEqual(self.post(accounts.validate_access,
            {"access_token": session["access_token"]}).status_code, 200)
        self.assertEqual(self.post(accounts.change_password, {
            "access_token": session["access_token"],
            "current_password": self.password,
            "new_password": secrets.token_urlsafe(28),
        }).status_code, 204)
        self.assertEqual(self.post(accounts.validate_access,
            {"access_token": session["access_token"]}).status_code, 200)

    def test_password_change_preserves_current_session_and_revokes_others_immediately(self):
        account = self.register_and_verify()
        current, other = [json.loads(self.post(accounts.login, {
            "email": account.email, "password": self.password}).content) for _ in range(2)]
        proof = self.post(accounts.reauthenticate, {
            "access_token": current["access_token"], "current_password": self.password})
        self.assertEqual(proof.status_code, 200)
        password = secrets.token_urlsafe(28)
        self.assertEqual(self.post(accounts.change_password, {
            "access_token": current["access_token"], "current_password": self.password,
            "new_password": password}).status_code, 204)
        for tokens, expected in ((current, 200), (other, 401)):
            self.assertEqual(self.post(accounts.validate_access,
                {"access_token": tokens["access_token"]}).status_code, expected)
            self.assertEqual(self.post(accounts.refresh,
                {"refresh_token": tokens["refresh_token"]}).status_code, expected)
        self.assertFalse(ReauthenticationToken.objects.filter(used_at__isnull=True).exists())
        self.assertEqual(self.post(accounts.login, {
            "email": account.email, "password": self.password}).status_code, 401)
        self.assertEqual(self.post(accounts.login, {
            "email": account.email, "password": password}).status_code, 200)
        self.assertTrue(AuditDelivery.objects.filter(event__kind="account.password_changed").exists())

    def test_profile_update_is_owned_and_rejects_client_role(self):
        account = self.register_and_verify()
        session = json.loads(self.post(accounts.login,
            {"email": account.email, "password": self.password}).content)
        self.assertEqual(self.post(accounts.update_profile, {
            "access_token": session["access_token"], "display_name": "New Name",
            "role": "administrator",
        }).status_code, 400)
        response = self.post(accounts.update_profile, {
            "access_token": session["access_token"], "display_name": "New Name",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["user"]["display_name"], "New Name")
        account.refresh_from_db()
        self.assertEqual(account.display_name, "New Name")
        self.assertEqual(account.role, Account.Role.VIEWER)

    def test_mail_failure_rolls_back_registration(self):
        with patch("service.accounts.send_mail", side_effect=smtplib.SMTPException), \
                self.assertLogs("service.accounts", level="ERROR"):
            response = self.post(accounts.register, {"email": "user@example.test",
                "password": self.password, "display_name": "Viewer"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Account.objects.exists())
        self.assertFalse(EmailVerification.objects.exists())

    def test_reset_delivery_failure_is_generic_and_preserves_previous_code(self):
        account = self.register_and_verify()
        self.post(accounts.request_password_reset, {"email": account.email})
        previous = PasswordReset.objects.get()
        PasswordReset.objects.filter(pk=previous.pk).update(
            created_at=timezone.now() - accounts.CODE_RESEND_COOLDOWN - timedelta(seconds=1))
        with patch("service.accounts.send_mail", side_effect=smtplib.SMTPException), \
                self.assertLogs("service.accounts", level="ERROR"):
            response = self.post(accounts.request_password_reset, {"email": account.email})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(PasswordReset.objects.count(), 1)
        previous.refresh_from_db()
        self.assertIsNone(previous.used_at)
        unknown = self.post(accounts.request_password_reset, {"email": "unknown@example.test"})
        self.assertEqual((response.status_code, response.content), (unknown.status_code, unknown.content))

    def test_resend_delivery_failure_preserves_previous_code_and_does_not_disclose_account(self):
        self.post(accounts.register, {"email": "viewer@example.test", "password": self.password,
                                       "display_name": "Viewer"})
        code = self.code_from(mail.outbox[-1])
        EmailVerification.objects.update(
            created_at=timezone.now() - accounts.CODE_RESEND_COOLDOWN - timedelta(seconds=1))
        with patch("service.accounts.send_mail", side_effect=smtplib.SMTPException), \
                self.assertLogs("service.accounts", level="ERROR"):
            response = self.post(accounts.resend_verification, {"email": "viewer@example.test"})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(EmailVerification.objects.count(), 1)
        self.assertIsNone(EmailVerification.objects.get().used_at)
        self.assertEqual(self.post(accounts.verify_email, {"email": "viewer@example.test", "code": code}).status_code, 200)

    def test_expired_verification_cannot_activate_account(self):
        self.post(accounts.register, {"email": "user@example.test",
            "password": self.password, "display_name": "Viewer"})
        EmailVerification.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        code = self.code_from(mail.outbox[0])
        self.assertEqual(self.post(accounts.verify_email, {"email": "user@example.test", "code": code}).status_code, 400)
        self.assertFalse(Account.objects.get().is_active)

    def test_resend_is_generic_throttled_and_replaces_the_old_code(self):
        email = "user@example.test"
        self.post(accounts.register, {"email": email,
            "password": self.password, "display_name": "Viewer"})
        old_code = self.code_from(mail.outbox[0])
        for address in (email, "unknown@example.test"):
            self.assertEqual(self.post(accounts.resend_verification, {"email": address}).status_code, 204)
        self.assertEqual(len(mail.outbox), 1)
        EmailVerification.objects.update(
            created_at=timezone.now() - accounts.CODE_RESEND_COOLDOWN - timedelta(seconds=1))
        self.assertEqual(self.post(accounts.resend_verification, {"email": email}).status_code, 204)
        self.assertEqual(len(mail.outbox), 2)
        new_code = self.code_from(mail.outbox[1])
        self.assertEqual(self.post(accounts.verify_email, {"email": email, "code": old_code}).status_code, 400)
        self.assertEqual(self.post(accounts.verify_email, {"email": email, "code": new_code}).status_code, 200)
        self.assertEqual(self.post(accounts.resend_verification, {"email": email}).status_code, 204)
        self.assertEqual(len(mail.outbox), 2)

    def code_from(self, message):
        found = re.search(r": ([0-9]{6})\n", message.body)
        self.assertIsNotNone(found)
        return found.group(1)

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
        code = self.code_from(mail.outbox[0])
        self.assertEqual(self.post(accounts.verify_email, {"email": "user@example.test", "code": code}).status_code, 200)
        account.refresh_from_db()
        self.assertTrue(account.is_active)
        self.assertIsNotNone(account.email_verified_at)
        self.assertEqual(self.post(accounts.verify_email, {"email": "user@example.test", "code": code}).status_code, 400)
        return account

    def test_registration_verification_and_duplicate(self):
        self.register_and_verify()
        response = self.post(accounts.register, {"email": "USER@example.test",
                                                  "password": self.password,
                                                  "display_name": "Someone Else"})
        self.assertEqual(response.status_code, 409)

    def test_session_management_scopes_listing_and_revocation_to_the_owner(self):
        account = self.register_and_verify()
        foreign = Account.objects.create_user("other@example.test", self.password, "Other")
        now = timezone.now()
        current, other, outsider = [
            LoginSession.objects.create(
                account=owner, refresh_digest=secrets.token_hex(32),
                expires_at=now + timedelta(days=1),
            )
            for owner in (account, account, foreign)
        ]
        token = accounts._issue(current)["access_token"]
        other_tokens = accounts._issue(other)
        data = {"access_token": token}
        result = self.post(accounts.manage_sessions, data)
        self.assertEqual(result.status_code, 200)
        rows = json.loads(result.content)["items"]
        self.assertEqual({row["id"]: row["current"] for row in rows},
                         {str(current.id): True, str(other.id): False})
        self.assertEqual(set(rows[0]), {"id", "created_at", "expires_at", "current"})
        for session, status in ((outsider, 404), (current, 409), (other, 204)):
            self.assertEqual(self.post(accounts.manage_sessions,
                {**data, "session_id": str(session.id)}).status_code, status)
        self.assertEqual(self.post(accounts.validate_access,
            {"access_token": other_tokens["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.refresh,
            {"refresh_token": other_tokens["refresh_token"]}).status_code, 401)
        outsider.refresh_from_db()
        self.assertIsNone(outsider.revoked_at)

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

    def sign_in(self, account):
        response = self.post(accounts.login, {"email": account.email, "password": self.password})
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def test_replay_of_an_old_refresh_token_revokes_the_family_and_the_newest_token(self):
        account = self.register_and_verify()
        first = self.sign_in(account)
        second = json.loads(self.post(accounts.refresh, {"refresh_token": first["refresh_token"]}).content)
        third = json.loads(self.post(accounts.refresh, {"refresh_token": second["refresh_token"]}).content)
        self.assertEqual(self.post(accounts.validate_access, {"access_token": third["access_token"]}).status_code, 200)
        # A stolen, long-rotated token is still recognised as a replay and ends the whole session.
        self.assertEqual(self.post(accounts.refresh, {"refresh_token": first["refresh_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.refresh, {"refresh_token": third["refresh_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.validate_access, {"access_token": third["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.revoke, {"refresh_token": third["refresh_token"]}).status_code, 401)
        self.assertEqual(SecurityEvent.objects.filter(kind="session.replay", actor_id=account.id).count(), 1)

    def test_replay_events_and_audit_rows_carry_no_token_material(self):
        account = self.register_and_verify()
        first = self.sign_in(account)
        second = json.loads(self.post(accounts.refresh, {"refresh_token": first["refresh_token"]}).content)
        self.post(accounts.refresh, {"refresh_token": first["refresh_token"]})
        stored = " ".join(str(value) for value in SecurityEvent.objects.values_list("kind", "actor_id"))
        for token in (first["refresh_token"], first["access_token"], second["refresh_token"], second["access_token"]):
            self.assertNotIn(token, stored)
            self.assertNotIn(token.split(".")[-1], stored)
        # The event table has no column that could hold a credential.
        self.assertEqual({field.name for field in SecurityEvent._meta.concrete_fields},
                         {"id", "actor_id", "kind", "occurred_at"})

    def test_a_wrong_refresh_token_cannot_revoke_someone_elses_session(self):
        account = self.register_and_verify()
        tokens = self.sign_in(account)
        session_id, _, secret = tokens["refresh_token"].partition(".")
        guesses = [f"{session_id}.{'A' * len(secret)}", f"{session_id}.{secret[::-1]}",
                   f"{uuid.uuid4()}.{secret}", f"{session_id}.", session_id]
        for guess in guesses:
            with self.subTest(guess=guess[:8]):
                self.assertEqual(self.post(accounts.refresh, {"refresh_token": guess}).status_code, 401)
                self.assertEqual(self.post(accounts.revoke, {"refresh_token": guess}).status_code, 401)
        # Knowing the session id is not enough to end, or to hijack, the session.
        self.assertEqual(self.post(accounts.validate_access, {"access_token": tokens["access_token"]}).status_code, 200)
        self.assertIsNone(LoginSession.objects.get().revoked_at)
        self.assertEqual(self.post(accounts.refresh, {"refresh_token": tokens["refresh_token"]}).status_code, 200)

    def test_signing_out_one_session_leaves_the_account_other_sessions_valid(self):
        account = self.register_and_verify()
        phone, tablet = self.sign_in(account), self.sign_in(account)
        self.assertEqual(self.post(accounts.revoke, {"access_token": phone["access_token"]}).status_code, 204)
        self.assertEqual(self.post(accounts.revoke, {"access_token": phone["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.validate_access, {"access_token": tablet["access_token"]}).status_code, 200)
        self.assertEqual(self.post(accounts.refresh, {"refresh_token": tablet["refresh_token"]}).status_code, 200)

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
        tokens = json.loads(self.post(accounts.login, {"email": "user@example.test",
                                                     "password": self.password}).content)
        token = tokens["access_token"]
        self.assertEqual(self.post(accounts.revoke, {"access_token": token}).status_code, 204)
        self.assertEqual(self.post(accounts.validate_access,
                                   {"access_token": token}).status_code, 401)
        self.assertEqual(self.post(accounts.refresh,
            {"refresh_token": tokens["refresh_token"]}).status_code, 401)
        self.assertTrue(AuditDelivery.objects.filter(event__kind="session.revoked").exists())

    def test_logout_by_refresh_also_revokes_access_and_has_no_body(self):
        account = self.register_and_verify()
        tokens = json.loads(self.post(accounts.login, {
            "email": account.email, "password": self.password}).content)
        response = self.post(accounts.revoke, {"refresh_token": tokens["refresh_token"]})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.post(accounts.validate_access,
            {"access_token": tokens["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.refresh,
            {"refresh_token": tokens["refresh_token"]}).status_code, 401)

    def test_security_actions_have_matching_secret_free_audit_deliveries(self):
        account = self.register_and_verify()
        tokens = json.loads(self.post(accounts.login, {
            "email": account.email, "password": self.password}).content)
        access = {"access_token": tokens["access_token"]}
        self.post(accounts.update_profile, {**access, "display_name": "Updated Name"})
        self.post(accounts.manage_sessions, access)
        self.post(accounts.revoke, access)
        expected = {"account.registered", "account.verified", "login.succeeded",
                    "account.profile_updated", "session.listed", "session.revoked"}
        self.assertEqual(set(SecurityEvent.objects.values_list("kind", flat=True)), expected)
        self.assertEqual(SecurityEvent.objects.count(), AuditDelivery.objects.count())
        self.assertTrue(all(actor == account.id for actor in
                            SecurityEvent.objects.values_list("actor_id", flat=True)))

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
