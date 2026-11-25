import json
import os
import secrets
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pyotp
from cryptography.fernet import Fernet
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from service import account_lookup, accounts
from service.models import Account, LoginSession, SecurityEvent, TotpFactor


@override_settings(STAGING_PRIVILEGED=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountLookupTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        key = Fernet.generate_key()
        path = Path(temporary.name) / "mfa-key"
        path.touch(mode=0o600)
        path.write_bytes(key)
        environment = patch.dict(os.environ, {"KOLOVIBE_MFA_ENCRYPTION_KEY_FILE": str(path)})
        environment.start()
        self.addCleanup(environment.stop)
        self.key = key
        self.access = {role: self.session(role) for role in ("administrator", "moderator")}
        self.viewer = Account.objects.create_user("ada@example.test", secrets.token_urlsafe(32), "Ada Eze")
        self.viewer.email_verified_at = self.now
        self.viewer.save()

    def session(self, role):
        account = Account.objects.create_user(f"{role}@example.test", secrets.token_urlsafe(32), role.title())
        account.role = role
        account.save()
        TotpFactor.objects.create(account=account, encrypted_secret=Fernet(self.key).encrypt(pyotp.random_base32().encode()).decode())
        login = LoginSession.objects.create(account=account, authenticated_role=role, mfa_verified_at=self.now,
                                            expires_at=self.now + timedelta(minutes=15), refresh_digest=secrets.token_hex(32))
        return accounts._issue(login)["access_token"]

    def call(self, email, token=None, **extra):
        body = {"access_token": token or self.access["administrator"], "email": email, **extra}
        return account_lookup.lookup(RequestFactory().post("/internal/auth/account-lookup", json.dumps(body), content_type="application/json"))

    def test_administrator_finds_an_eligible_account_by_exact_email_and_every_lookup_is_audited(self):
        response = self.call("  ADA@example.test ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"account_id": str(self.viewer.id), "display_name": "Ada Eze",
                                                        "role": "viewer", "email_verified": True})
        self.assertEqual(SecurityEvent.objects.filter(kind="account.creator_candidate_looked_up").count(), 1)
        self.assertNotIn("ada@example.test", response.content.decode().replace(str(self.viewer.id), ""))

    def test_unknown_inactive_and_privileged_accounts_are_indistinguishable(self):
        inactive = Account.objects.create_user("gone@example.test", secrets.token_urlsafe(32), "Gone")
        inactive.is_active = False
        inactive.save()
        answers = {self.call(email).content for email in
                   ("nobody@example.test", "gone@example.test", "moderator@example.test", "administrator@example.test")}
        self.assertEqual(answers, {json.dumps({"detail": "Account unavailable"}).encode()})

    def test_only_administrators_may_look_up_and_bad_requests_are_rejected(self):
        self.assertEqual(self.call("ada@example.test", token=self.access["moderator"]).status_code, 403)
        self.assertEqual(self.call("ada@example.test", token="invalid").status_code, 401)
        for email in ("", "not-an-email", "a" * 300 + "@example.test", None):
            self.assertEqual(self.call(email).status_code, 400, email)
            # Phase 11 D11-005: authority is decided before the body is judged, so a caller without it learns nothing about the schema
            self.assertEqual(self.call(email, token=self.access["moderator"]).status_code, 403, email)
            self.assertEqual(self.call(email, token="invalid").status_code, 401, email)
        self.assertEqual(self.call("ada@example.test", extra="field").status_code, 400)

    def test_lookups_are_rate_limited_per_administrator(self):
        statuses = [self.call("nobody@example.test").status_code for _ in range(31)]
        self.assertEqual(statuses[:30], [404] * 30)
        self.assertEqual(statuses[30], 429)
        self.assertEqual(self.call("ada@example.test", token=self.access["moderator"]).status_code, 403)
