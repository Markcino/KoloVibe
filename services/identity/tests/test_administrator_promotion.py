import base64
from datetime import timedelta
from io import StringIO
import json
import os
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from service.models import Account, AuditDelivery, LoginSession, MfaChallenge, RecoveryCode, SecurityEvent, TotpFactor


@override_settings(STAGING_PRIVILEGED=True)
class AdministratorPromotionTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create_user(
            "moderator@example.test", secrets.token_urlsafe(32), "Moderator")
        self.account.role = Account.Role.MODERATOR
        self.account.email_verified_at = timezone.now()
        self.account.save(update_fields=["role", "email_verified_at"])
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        key = Fernet.generate_key()
        key_path = Path(self.directory.name) / "key"
        key_path.touch(mode=0o600)
        key_path.write_bytes(key)
        environment = patch.dict(os.environ, {"KOLOVIBE_MFA_ENCRYPTION_KEY_FILE": str(key_path)})
        environment.start()
        self.addCleanup(environment.stop)
        self.factor = TotpFactor.objects.create(account=self.account, last_step=10,
            encrypted_secret=Fernet(key).encrypt(base64.b32encode(b"promotion-test-factor")).decode())
        self.recovery = RecoveryCode.objects.create(account=self.account, digest=secrets.token_hex(32))
        self.session = LoginSession.objects.create(account=self.account, authenticated_role="moderator",
            mfa_verified_at=timezone.now(), refresh_digest=secrets.token_hex(32),
            expires_at=timezone.now() + timedelta(minutes=15))
        self.challenge = MfaChallenge.objects.create(account=self.account, role="moderator",
            digest=secrets.token_hex(32), throttle_key=secrets.token_hex(32),
            expires_at=timezone.now() + timedelta(minutes=5))

    def promote(self, apply=False):
        stream = StringIO()
        call_command("promote_moderator_to_administrator", email=self.account.email,
                     approval_reference="OWNER-TEST-PROMOTION", apply=apply, stdout=stream)
        return json.loads(stream.getvalue())

    def test_promotion_preserves_factor_password_and_recovery_and_invalidates_sessions(self):
        password = self.account.password
        result = self.promote(apply=True)
        self.account.refresh_from_db()
        self.session.refresh_from_db()
        self.challenge.refresh_from_db()
        factor = TotpFactor.objects.get(account=self.account)
        self.assertEqual(self.account.role, "administrator")
        self.assertEqual(self.account.password, password)
        self.assertFalse(self.account.is_superuser)
        self.assertEqual((factor.encrypted_secret, factor.last_step), (self.factor.encrypted_secret, 10))
        self.assertTrue(RecoveryCode.objects.filter(pk=self.recovery.pk, used_at__isnull=True).exists())
        self.assertIsNotNone(self.session.revoked_at)
        self.assertIsNotNone(self.challenge.used_at)
        event = SecurityEvent.objects.get(pk=result["audit_event_id"])
        self.assertEqual(event.kind, "account.administrator_role_granted")
        self.assertTrue(AuditDelivery.objects.filter(event=event).exists())
        self.assertEqual(self.promote(apply=True)["status"], "already-administrator")
        self.assertEqual(SecurityEvent.objects.count(), 1)

    def test_dry_run_has_no_role_session_or_audit_effect(self):
        self.assertEqual(self.promote()["status"], "dry-run")
        self.account.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(self.account.role, "moderator")
        self.assertIsNone(self.session.revoked_at)
        self.assertFalse(SecurityEvent.objects.exists())

    def test_missing_or_unusable_mfa_and_unverified_accounts_fail_closed(self):
        self.factor.encrypted_secret = "unusable"
        self.factor.save(update_fields=["encrypted_secret"])
        with self.assertRaises(CommandError):
            self.promote(apply=True)
        self.factor.delete()
        with self.assertRaises(CommandError):
            self.promote(apply=True)
        self.account.refresh_from_db()
        self.assertEqual(self.account.role, "moderator")
        self.assertFalse(SecurityEvent.objects.exists())

    def test_audit_failure_rolls_back_role_and_revocations(self):
        with patch("service.management.commands.promote_moderator_to_administrator.record",
                   side_effect=RuntimeError), self.assertRaises(CommandError):
            self.promote(apply=True)
        self.account.refresh_from_db()
        self.session.refresh_from_db()
        self.challenge.refresh_from_db()
        self.assertEqual(self.account.role, "moderator")
        self.assertIsNone(self.session.revoked_at)
        self.assertIsNone(self.challenge.used_at)

    def test_inactive_unverified_and_ordinary_accounts_cannot_be_promoted(self):
        for fields in ({"is_active": False}, {"email_verified_at": None}, {"role": "viewer"}):
            with self.subTest(fields=fields):
                original = {key: getattr(self.account, key) for key in fields}
                Account.objects.filter(pk=self.account.pk).update(**fields)
                with self.assertRaises(CommandError):
                    self.promote(apply=True)
                Account.objects.filter(pk=self.account.pk).update(**original)
        self.assertFalse(SecurityEvent.objects.exists())

    @override_settings(STAGING_PRIVILEGED=False)
    def test_disabled_privileged_access_rejects_promotion(self):
        with self.assertRaises(CommandError):
            self.promote(apply=True)
