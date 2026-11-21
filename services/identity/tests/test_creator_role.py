from datetime import timedelta
import json
import secrets
from uuid import uuid4
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils import timezone

from service.accounts import _issue, _session_for_access, refresh, sync_creator_role
from service.models import Account, AuditDelivery, LoginSession, ReauthenticationToken, SecurityEvent


class CreatorRoleTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create_user("creator@example.test", secrets.token_urlsafe(32), "Creator")
        self.account.email_verified_at = timezone.now()
        self.account.save(update_fields=["email_verified_at"])
        self.evidence = {"account_id": str(self.account.id), "creator_id": str(uuid4()), "upload_eligible": True}

    def call(self, caller="gateway", **changes):
        request = RequestFactory().post("/internal/auth/creator-role", self.evidence | changes,
                                        content_type="application/json")
        request.service_caller = caller
        return sync_creator_role(request)

    def session(self):
        session = LoginSession.objects.create(account=self.account, authenticated_role=self.account.role,
                    refresh_digest=secrets.token_hex(32), expires_at=timezone.now() + timedelta(days=1))
        return session, _issue(session)

    def test_atomic_audited_grant_revokes_access_refresh_and_reauthentication(self):
        session, tokens = self.session()
        other, _ = self.session()
        proof = ReauthenticationToken.objects.create(account=self.account, session=session,
                    digest=secrets.token_hex(32), expires_at=timezone.now() + timedelta(minutes=5))
        self.assertIsNotNone(_session_for_access(tokens["access_token"]))
        self.assertEqual(json.loads(self.call().content)["changed"], True)
        self.account.refresh_from_db()
        self.assertEqual(self.account.role, "creator")
        self.assertFalse(LoginSession.objects.filter(pk__in=[session.pk, other.pk], revoked_at__isnull=True).exists())
        self.assertIsNone(_session_for_access(tokens["access_token"]))
        request = RequestFactory().post("/internal/auth/refresh", {"refresh_token": tokens["refresh_token"]},
                                       content_type="application/json")
        self.assertEqual(refresh(request).status_code, 401)
        proof.refresh_from_db()
        self.assertIsNotNone(proof.used_at)
        self.assertEqual(SecurityEvent.objects.get().kind, "account.creator_role_granted")
        self.assertEqual(AuditDelivery.objects.count(), 1)
        new_session, fresh = self.session()
        self.assertIsNotNone(_session_for_access(fresh["access_token"]))
        self.assertEqual(json.loads(self.call().content)["changed"], False)
        new_session.refresh_from_db()
        self.assertIsNone(new_session.revoked_at)
        self.assertEqual(SecurityEvent.objects.count(), 1)

    def test_no_other_caller_role_or_unverified_account_can_be_promoted(self):
        for caller in (None, "creators", "content"):
            self.assertEqual(self.call(caller=caller).status_code, 403)
        self.assertEqual(self.call(upload_eligible=False).status_code, 403)
        self.assertEqual(self.call(role="administrator").status_code, 400)
        self.assertEqual(self.call(creator_id=None).status_code, 400)
        for fields in ({"email_verified_at": None}, {"is_active": False}, {"is_staff": True},
                       {"is_superuser": True}, {"role": "moderator"}, {"role": "administrator"}):
            with self.subTest(fields=fields):
                Account.objects.filter(pk=self.account.pk).update(**fields)
                self.assertEqual(self.call().status_code, 403)
                Account.objects.filter(pk=self.account.pk).update(email_verified_at=timezone.now(),
                    is_active=True, is_staff=False, is_superuser=False, role="viewer")
        self.assertFalse(SecurityEvent.objects.exists())

    @patch("service.accounts.record", side_effect=RuntimeError("audit unavailable"))
    def test_audit_failure_rolls_back_role_and_session_revocation(self, record):
        session, tokens = self.session()
        with self.assertRaises(RuntimeError):
            self.call()
        self.account.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(self.account.role, "viewer")
        self.assertIsNone(session.revoked_at)
        self.assertIsNotNone(_session_for_access(tokens["access_token"]))
