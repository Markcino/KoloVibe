from datetime import timedelta
import base64
import json
import os
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch
from datetime import datetime, timezone as datetime_timezone

from cryptography.fernet import Fernet
from django.core.management import call_command, CommandError
from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
import pyotp

from service import accounts
from service.mfa import verify_mfa
from service.models import (Account, AuditDelivery, LoginSession, MfaChallenge,
                            RecoveryCode, SecurityEvent, TotpFactor)


@override_settings(STAGING_PRIVILEGED=True)
class MfaAuditTests(TestCase):
    def setUp(self):
        # The replay assertions must use the same TOTP step, even across a slow
        # full-suite run. Freeze both issuer and verifier clocks, never the result
        # of factor verification. Production's replay checks remain exercised.
        self.now = datetime(2026, 11, 11, 12, 0, 10, tzinfo=datetime_timezone.utc)
        for clock, value in (("service.mfa.time.time", self.now.timestamp()),
                             ("django.utils.timezone.now", self.now)):
            mocked_clock = patch(clock, return_value=value)
            mocked_clock.start()
            self.addCleanup(mocked_clock.stop)
        self.factory = RequestFactory()
        self.password = secrets.token_urlsafe(32)
        self.account = Account.objects.create_user("reviewer@example.test", self.password, "Reviewer")
        self.account.role = Account.Role.MODERATOR
        self.account.save(update_fields=["role"])
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        key_path = Path(self.temporary.name) / "encryption"
        key_path.touch(mode=0o600)
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        self.environment = patch.dict(os.environ, {"KOLOVIBE_MFA_ENCRYPTION_KEY_FILE": str(key_path)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.factor = base64.b32encode(b"test-only KoloVibe TOTP factor").decode()
        TotpFactor.objects.create(account=self.account,
                                  encrypted_secret=Fernet(key).encrypt(self.factor.encode()).decode())

    def post(self, view, data):
        return view(self.factory.post("/internal/auth/test", json.dumps(data),
                                      content_type="application/json", REMOTE_ADDR="127.0.0.1"))

    def challenge(self):
        response = self.post(accounts.login, {"email": self.account.email, "password": self.password})
        self.assertEqual(response.status_code, 202)
        payload = json.loads(response.content)
        self.assertNotIn("access_token", payload)
        return payload["challenge_token"]

    def verify(self, raw, code=None):
        return self.post(verify_mfa, {"challenge_token": raw,
                                     "code": code if code is not None else pyotp.TOTP(self.factor).at(self.now)})

    def test_password_is_insufficient_and_mfa_challenge_is_one_use(self):
        challenge = self.challenge()
        self.assertEqual(LoginSession.objects.count(), 0)
        response = self.verify(challenge)
        self.assertEqual(response.status_code, 200)
        token = json.loads(response.content)["access_token"]
        self.assertEqual(self.post(accounts.validate_access, {"access_token": token}).status_code, 200)
        self.assertEqual(self.verify(challenge).status_code, 401)
        self.assertEqual(self.verify(self.challenge()).status_code, 401)
        self.assertTrue(SecurityEvent.objects.filter(kind="mfa.succeeded").exists())
        self.assertEqual(SecurityEvent.objects.count(), AuditDelivery.objects.count())

    def test_consumed_totp_stays_rejected_after_clock_advances_but_new_step_works(self):
        code = pyotp.TOTP(self.factor).at(self.now)
        self.assertEqual(self.verify(self.challenge(), code).status_code, 200)
        next_challenge = self.challenge()
        next_time = self.now + timedelta(seconds=30)
        with patch("service.mfa.time.time", return_value=next_time.timestamp()):
            self.assertEqual(self.verify(next_challenge, code).status_code, 401)
            self.assertEqual(self.verify(next_challenge, pyotp.TOTP(self.factor).at(next_time)).status_code, 200)

    def test_unused_previous_period_code_is_rejected_and_audited(self):
        challenge = self.challenge()
        code = pyotp.TOTP(self.factor).at(self.now - timedelta(seconds=30))
        self.assertEqual(self.verify(challenge, code).status_code, 401)
        self.assertEqual(TotpFactor.objects.get().last_step, -1)
        self.assertFalse(LoginSession.objects.exists())
        self.assertTrue(SecurityEvent.objects.filter(kind="mfa.failed").exists())
        self.assertEqual(self.verify(challenge).status_code, 200)

    def test_unused_future_period_code_is_rejected_without_consuming_it(self):
        challenge = self.challenge()
        future = self.now.replace(second=30)
        code = pyotp.TOTP(self.factor).at(future)
        self.assertEqual(self.verify(challenge, code).status_code, 401)
        self.assertEqual(TotpFactor.objects.get().last_step, -1)
        self.assertFalse(LoginSession.objects.exists())
        self.assertTrue(SecurityEvent.objects.filter(kind="mfa.failed").exists())
        with patch("service.mfa.time.time", return_value=future.timestamp()):
            self.assertEqual(self.verify(challenge, code).status_code, 200)

    def test_current_period_code_is_valid_until_the_boundary_and_only_once(self):
        last_instant = self.now.replace(second=29, microsecond=999999)
        code = pyotp.TOTP(self.factor).at(self.now)
        with patch("service.mfa.time.time", return_value=last_instant.timestamp()):
            self.assertEqual(self.verify(self.challenge(), code).status_code, 200)
            self.assertEqual(self.verify(self.challenge(), code).status_code, 401)
        self.assertEqual(TotpFactor.objects.get().last_step, int(self.now.timestamp()) // 30)

    def test_unused_code_expires_at_exact_boundary_and_new_period_starts(self):
        challenge = self.challenge()
        code = pyotp.TOTP(self.factor).at(self.now)
        boundary = self.now.replace(second=30)
        with patch("service.mfa.time.time", return_value=boundary.timestamp()):
            self.assertEqual(self.verify(challenge, code).status_code, 401)
            self.assertEqual(TotpFactor.objects.get().last_step, -1)
            self.assertFalse(LoginSession.objects.exists())
            self.assertTrue(SecurityEvent.objects.filter(kind="mfa.failed").exists())
            current_code = pyotp.TOTP(self.factor).at(boundary)
            self.assertEqual(self.verify(challenge, current_code).status_code, 200)
        self.assertEqual(TotpFactor.objects.get().last_step, int(boundary.timestamp()) // 30)

    def test_challenge_expiry_role_changes_and_attempt_limit(self):
        challenge = self.challenge()
        for _ in range(5):
            self.assertEqual(self.verify(challenge, "bad-code").status_code, 401)
        self.assertEqual(self.verify(challenge).status_code, 429)
        MfaChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.verify(challenge).status_code, 401)
        challenge = self.challenge()
        self.account.role = Account.Role.ADMINISTRATOR
        self.account.save(update_fields=["role"])
        self.assertEqual(self.verify(challenge).status_code, 401)

    def test_recovery_code_is_hashed_and_single_use(self):
        raw = secrets.token_urlsafe(32)
        RecoveryCode.objects.create(account=self.account, digest=accounts._digest("recovery:" + raw))
        response = self.verify(self.challenge(), raw)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.verify(self.challenge(), raw).status_code, 401)
        self.assertIsNotNone(RecoveryCode.objects.get().used_at)
        self.assertTrue(SecurityEvent.objects.filter(kind="mfa.recovery_used").exists())
        self.assertNotIn(raw, RecoveryCode.objects.get().digest)

    def test_privileged_session_cannot_extend_mfa_lifetime_or_change_role(self):
        tokens = json.loads(self.verify(self.challenge()).content)
        LoginSession.objects.update(mfa_verified_at=timezone.now() - timedelta(seconds=901))
        self.assertEqual(self.post(accounts.refresh, {"refresh_token": tokens["refresh_token"]}).status_code, 403)
        self.assertEqual(self.post(accounts.validate_access, {"access_token": tokens["access_token"]}).status_code, 401)
        LoginSession.objects.update(mfa_verified_at=timezone.now())
        self.account.role = Account.Role.ADMINISTRATOR
        self.account.save(update_fields=["role"])
        self.assertEqual(self.post(accounts.validate_access, {"access_token": tokens["access_token"]}).status_code, 401)

    def test_wrong_password_cannot_get_challenge_and_wrong_encryption_fails_closed(self):
        self.assertEqual(self.post(accounts.login, {"email": self.account.email,
                                                    "password": secrets.token_urlsafe(32)}).status_code, 401)
        self.assertFalse(MfaChallenge.objects.exists())
        raw = self.challenge()
        TotpFactor.objects.update(encrypted_secret=secrets.token_urlsafe(32))
        with self.assertLogs("service.mfa", level="ERROR"):
            self.assertEqual(self.verify(raw).status_code, 503)
        self.assertFalse(LoginSession.objects.exists())

    def test_staff_cannot_bypass_role_mfa_and_removed_factor_invalidates_session(self):
        tokens = json.loads(self.verify(self.challenge()).content)
        TotpFactor.objects.all().delete()
        self.assertEqual(self.post(accounts.validate_access,
                                  {"access_token": tokens["access_token"]}).status_code, 401)
        self.account.role = Account.Role.VIEWER
        self.account.is_staff = True
        self.account.save(update_fields=["role", "is_staff"])
        self.assertEqual(self.post(accounts.login, {"email": self.account.email,
                                                   "password": self.password}).status_code, 403)

    @override_settings(STAGING_PRIVILEGED=False)
    def test_privileged_routes_stay_gated(self):
        self.assertEqual(self.post(accounts.login, {"email": self.account.email,
                                                   "password": self.password}).status_code, 403)
        self.assertEqual(self.verify("x" * 48).status_code, 403)

    def test_security_events_reject_orm_sql_updates_and_deletes(self):
        self.challenge()
        event = SecurityEvent.objects.first()
        for operation in (lambda: SecurityEvent.objects.filter(id=event.id).update(kind="login.failed"),
                          lambda: SecurityEvent.objects.filter(id=event.id)._raw_delete("default")):
            with self.assertRaises(DatabaseError), transaction.atomic():
                operation()

    def test_audit_delivery_retries_and_preserves_immutable_event(self):
        self.challenge()
        with patch("service.management.commands.deliver_security_audit.signed_internal_request",
                   side_effect=OSError), self.assertLogs(level="ERROR"), self.assertRaises(CommandError):
            call_command("deliver_security_audit")
        self.assertTrue(AuditDelivery.objects.filter(attempts=1, delivered_at__isnull=True).exists())
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.status = 201
        response.__enter__.return_value.read.return_value = b'{"status": "ok"}'
        with patch("service.management.commands.deliver_security_audit.signed_internal_request",
                   return_value=response) as client:
            call_command("deliver_security_audit")
            payload = json.loads(client.call_args.kwargs["payload"])
            self.assertEqual(set(payload), {"id", "actor_id", "kind", "occurred_at"})
        self.assertFalse(AuditDelivery.objects.filter(delivered_at__isnull=True).exists())

    def test_offline_enrollment_does_not_print_secrets_or_overwrite_files(self):
        TotpFactor.objects.all().delete()
        base = Path(self.temporary.name)
        secret_file, code_file = base / "factor", base / "code"
        for path, value in ((secret_file, self.factor), (code_file, pyotp.TOTP(self.factor).at(self.now))):
            path.touch(mode=0o600)
            path.write_text(value)
        output = base / "recovery"
        with patch.dict(os.environ, {"KOLOVIBE_ENROLLMENT_SECRET_FILE": str(secret_file),
                                     "KOLOVIBE_ENROLLMENT_CODE_FILE": str(code_file)}):
            with patch("service.management.commands.enroll_privileged_mfa.record",
                       side_effect=DatabaseError), self.assertRaises(CommandError):
                call_command("enroll_privileged_mfa", account_id=str(self.account.id),
                             recovery_file=str(output), approval_reference="fixture-owner-approval")
            self.assertFalse(output.exists())
            self.assertFalse(TotpFactor.objects.exists())
            self.assertFalse(RecoveryCode.objects.exists())
            call_command("enroll_privileged_mfa", account_id=str(self.account.id),
                         recovery_file=str(output), approval_reference="fixture-owner-approval")
            self.assertEqual(len(output.read_text().splitlines()), 10)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            original = output.read_text()
            with self.assertRaises(CommandError):
                call_command("enroll_privileged_mfa", account_id=str(self.account.id),
                             recovery_file=str(output), approval_reference="fixture-owner-approval")
            self.assertEqual(output.read_text(), original)
