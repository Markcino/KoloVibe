import json
import os
import re
import secrets
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pyotp
from cryptography.fernet import Fernet
from django.core import mail
from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from service import accounts, moderator_invitations as invitations
from service.models import (Account, AuditDelivery, LoginSession, ModeratorInvitation,
                            ModeratorInvitationEvent, RecoveryCode, SecurityEvent, TotpFactor)


@override_settings(STAGING_PRIVILEGED=True, EMAIL_HOST="smtp.fixture", DEFAULT_FROM_EMAIL="noreply@example.test",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ModeratorInvitationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.now = timezone.now().replace(second=10, microsecond=0)
        clock = patch("django.utils.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.key = Fernet.generate_key()
        path = Path(self.temporary.name) / "mfa-key"
        path.touch(mode=0o600)
        path.write_bytes(self.key)
        environment = patch.dict(os.environ, {"KOLOVIBE_MFA_ENCRYPTION_KEY_FILE": str(path)})
        environment.start()
        self.addCleanup(environment.stop)
        self.admin = Account.objects.create_user("admin@example.test", secrets.token_urlsafe(32), "Administrator")
        self.admin.role = Account.Role.ADMINISTRATOR
        self.admin.save()
        TotpFactor.objects.create(account=self.admin, encrypted_secret=Fernet(self.key).encrypt(pyotp.random_base32().encode()).decode())
        self.session = LoginSession.objects.create(account=self.admin, authenticated_role="administrator",
            mfa_verified_at=self.now, expires_at=self.now + timedelta(minutes=15), refresh_digest=secrets.token_hex(32))
        self.access = accounts._issue(self.session)["access_token"]
        self.password = secrets.token_urlsafe(32)
        self.data = {"access_token": self.access, "operation": "create", "key": secrets.token_urlsafe(32),
                     "email": "reviewer@example.test", "display_name": "Invited reviewer", "reason": "Pilot moderation team"}

    def post(self, view, data, **kwargs):
        return view(self.factory.post("/internal/auth/moderator-invitations", json.dumps(data),
                    content_type="application/json"), **kwargs)

    def create(self, **changes):
        response = self.post(invitations.administer, {**self.data, **changes})
        self.assertEqual(response.status_code, 202, response.content)
        token = re.search(r"\n([A-Za-z0-9_-]{64})\n", mail.outbox[-1].body).group(1)
        return ModeratorInvitation.objects.get(pk=json.loads(response.content)["id"]), token, response

    def begin(self, token, **changes):
        return self.post(invitations.accept, {"invitation_code": token, "email": self.data["email"],
                                             "password": self.password, **changes})

    def finish(self, token, code):
        return self.post(invitations.accept, {"invitation_code": token, "email": self.data["email"],
                                             "code": code}, complete=True)

    def test_mail_only_secret_idempotent_create_and_enrollment_before_activation(self):
        item, token, response = self.create()
        self.assertNotIn(token, response.content.decode())
        self.assertNotIn(token, item.token_digest)
        replay = self.post(invitations.administer, self.data)
        self.assertEqual(replay.content, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(SecurityEvent.objects.filter(kind="moderator.invitation_created").count(), 1)
        self.assertEqual(self.post(invitations.administer, {**self.data, "reason": "Different reason"}).status_code, 409)
        started = self.begin(token)
        self.assertEqual(started.status_code, 200)
        secret = json.loads(started.content)["secret"]
        item.refresh_from_db()
        self.assertNotIn(secret, item.encrypted_secret)
        self.assertNotIn(self.password, item.password_hash)
        self.assertFalse(Account.objects.filter(email=item.email).exists())
        for offset in (-30, 30):
            self.assertEqual(self.finish(token, pyotp.TOTP(secret).at(self.now + timedelta(seconds=offset))).status_code, 401)
        done = self.finish(token, pyotp.TOTP(secret).at(self.now))
        self.assertEqual(done.status_code, 200)
        account = Account.objects.get(email=item.email)
        self.assertEqual(account.role, Account.Role.MODERATOR)
        self.assertTrue(account.is_active and account.check_password(self.password))
        self.assertFalse(account.is_staff or account.is_superuser)
        self.assertEqual(account.email_verified_at, self.now)
        self.assertEqual(TotpFactor.objects.get(account=account).last_step, int(self.now.timestamp()) // 30)
        codes = json.loads(done.content)["recovery_codes"]
        self.assertEqual(len(codes), 10)
        self.assertEqual(RecoveryCode.objects.filter(account=account).count(), 10)
        self.assertFalse(RecoveryCode.objects.filter(digest__in=codes).exists())
        self.assertEqual(self.finish(token, pyotp.TOTP(secret).at(self.now)).status_code, 401)
        item.refresh_from_db()
        self.assertEqual((item.encrypted_secret, item.password_hash), ("", ""))
        login = self.post(accounts.login, {"email": item.email, "password": self.password})
        self.assertEqual(login.status_code, 202)
        self.assertNotIn("access_token", json.loads(login.content))
        self.assertTrue(ModeratorInvitationEvent.objects.filter(invitation=item, event__kind="moderator.invitation_accepted").exists())
        self.assertEqual(SecurityEvent.objects.count(), AuditDelivery.objects.count())

    def test_role_mfa_freshness_and_replay_are_checked_in_identity(self):
        item, token, _ = self.create()
        for role in ("moderator", "viewer", "creator"):
            self.admin.role = role
            self.admin.save()
            self.session.authenticated_role = role
            self.session.save()
            for operation in ({"operation": "list"}, self.data,
                              {"operation": "revoke", "id": str(item.id), "key": self.data["key"], "reason": "No longer needed"}):
                result = self.post(invitations.administer, {**operation, "access_token": self.access})
                self.assertEqual(result.status_code, 403)
        self.admin.role = "administrator"
        self.admin.save()
        self.session.authenticated_role = "administrator"
        self.session.mfa_verified_at = self.now - timedelta(minutes=5)
        self.session.save()
        self.assertEqual(self.post(invitations.administer, self.data).status_code, 403)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(SecurityEvent.objects.filter(kind="moderator.invitation_denied").exists())
        self.session.mfa_verified_at = None
        self.session.save()
        self.assertEqual(self.post(invitations.administer, self.data).status_code, 401)
        self.assertEqual(self.post(invitations.administer, {**self.data, "access_token": secrets.token_urlsafe(48)}).status_code, 401)

    def test_revocation_is_idempotent_and_blocks_setup_and_completion(self):
        item, token, _ = self.create()
        secret = json.loads(self.begin(token).content)["secret"]
        request = {"access_token": self.access, "operation": "revoke", "id": str(item.id),
                   "key": secrets.token_urlsafe(32), "reason": "Invitation sent in error"}
        for _ in range(2):
            self.assertEqual(self.post(invitations.administer, request).status_code, 204)
        self.assertEqual(SecurityEvent.objects.filter(kind="moderator.invitation_revoked").count(), 1)
        self.assertEqual(self.begin(token).status_code, 401)
        self.assertEqual(self.finish(token, pyotp.TOTP(secret).at(self.now)).status_code, 401)
        self.assertFalse(Account.objects.filter(email=item.email).exists())

    def test_expiry_wrong_mailbox_inviter_revocation_and_attempt_limit(self):
        item, token, _ = self.create()
        self.assertEqual(self.begin(token, email="other@example.test").status_code, 401)
        secret = json.loads(self.begin(token).content)["secret"]
        wrong = "%06d" % ((int(pyotp.TOTP(secret).at(self.now)) + 1) % 1000000)
        for _ in range(5):
            self.assertEqual(self.finish(token, wrong).status_code, 401)
        self.assertEqual(self.finish(token, pyotp.TOTP(secret).at(self.now)).status_code, 429)
        self.assertEqual(self.begin(token).status_code, 429)
        ModeratorInvitation.objects.filter(pk=item.id).update(expires_at=self.now)
        self.assertEqual(self.begin(token).status_code, 401)
        ModeratorInvitation.objects.filter(pk=item.id).update(expires_at=self.now + timedelta(hours=1), failures=0)
        self.admin.is_active = False
        self.admin.save()
        self.assertEqual(self.begin(token).status_code, 401)

    def test_setup_expiry_password_policy_and_existing_accounts_cannot_be_promoted(self):
        item, token, _ = self.create()
        self.assertEqual(self.begin(token, password=secrets.token_urlsafe(3)).status_code, 400)
        secret = json.loads(self.begin(token).content)["secret"]
        ModeratorInvitation.objects.filter(pk=item.id).update(setup_expires_at=self.now)
        self.assertEqual(self.finish(token, pyotp.TOTP(secret).at(self.now)).status_code, 401)
        Account.objects.create_user(item.email, secrets.token_urlsafe(32), "Existing viewer")
        self.assertEqual(self.begin(token).status_code, 409)
        self.assertEqual(Account.objects.get(email=item.email).role, "viewer")
        self.assertEqual(self.post(invitations.administer, {**self.data, "role": "administrator"}).status_code, 400)

    def test_list_is_masked_audited_and_does_not_expose_enrollment(self):
        item, token, _ = self.create()
        self.begin(token)
        result = self.post(invitations.administer, {"access_token": self.access, "operation": "list"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json.loads(result.content)["items"][0]["email_masked"], "r***@example.test")
        for value in (token, item.email, self.password):
            self.assertNotIn(value, result.content.decode())
        self.assertTrue(SecurityEvent.objects.filter(kind="moderator.invitation_listed").exists())

    def test_only_accepted_rows_expose_the_new_moderator_account_id(self):
        item, token, _ = self.create()
        listed = lambda: json.loads(self.post(invitations.administer, {"access_token": self.access, "operation": "list"}).content)["items"][0]
        self.assertNotIn("account_id", listed())
        secret = json.loads(self.begin(token).content)["secret"]
        self.assertEqual(self.finish(token, pyotp.TOTP(secret).at(self.now)).status_code, 200)
        row = listed()
        self.assertEqual(row["status"], "accepted")
        self.assertEqual(row["account_id"], str(Account.objects.get(email=item.email).id))
        self.assertEqual(set(row), {"id", "display_name", "email_masked", "status", "expires_at", "account_id"})

    def test_send_failure_rolls_back_invitation_and_success_event(self):
        with patch("service.moderator_invitations.send_mail", side_effect=OSError("fixture outage")):
            with self.assertLogs("service.moderator_invitations", level="ERROR"):
                result = self.post(invitations.administer, self.data)
        self.assertEqual(result.status_code, 503)
        self.assertFalse(ModeratorInvitation.objects.exists())
        self.assertFalse(SecurityEvent.objects.filter(kind="moderator.invitation_created").exists())

    def test_invites_are_bounded_per_administrator(self):
        for number in range(5):
            self.create(email=f"reviewer-{number}@example.test", key=secrets.token_urlsafe(32))
        self.assertEqual(self.post(invitations.administer, self.data).status_code, 429)

    def test_invitation_event_correlation_is_append_only(self):
        self.create()
        with self.assertRaises(DatabaseError), transaction.atomic():
            ModeratorInvitationEvent.objects.all().update(invitation_id=secrets.token_hex(16))
