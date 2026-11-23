from datetime import timedelta
from io import StringIO
import json
import secrets
from unittest.mock import patch
import uuid

from django.core.management import call_command, CommandError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import accounts, retention
from service.models import (Account, AuditDelivery, EmailVerification, LoginSession, LoginThrottle, MfaChallenge,
                            PasswordReset, ReauthenticationToken, SecurityEvent, UsedRefreshToken)

DAY = timedelta(days=1)


class RetentionTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.account = Account.objects.create_user("keep@example.test", secrets.token_urlsafe(24), "Keep")

    def digest(self):
        return secrets.token_hex(32)

    def session(self, **fields):
        return LoginSession.objects.create(account=self.account, refresh_digest=self.digest(),
                                           expires_at=fields.pop("expires_at", self.now + DAY), **fields)

    def make_rows(self, age):
        """One row of every purgeable kind whose usefulness ended `age` ago."""
        end = self.now - age
        LoginThrottle.objects.create(key=self.digest(), window_started_at=end)
        UsedRefreshToken.objects.create(digest=self.digest(), family_id=uuid.uuid4(), expires_at=end)
        MfaChallenge.objects.create(digest=self.digest(), account=self.account, role="moderator",
                                    throttle_key=self.digest(), expires_at=end)
        EmailVerification.objects.create(digest=self.digest(), account=self.account, expires_at=end)
        PasswordReset.objects.create(digest=self.digest(), account=self.account, expires_at=end)
        session = self.session(expires_at=end)
        ReauthenticationToken.objects.create(digest=self.digest(), account=self.account, session=session, expires_at=end)

    def counts(self):
        return {model.__name__: model.objects.count() for model in (
            LoginThrottle, UsedRefreshToken, MfaChallenge, EmailVerification, PasswordReset, ReauthenticationToken)}

    def test_old_rows_are_removed_and_recent_rows_are_kept(self):
        self.make_rows(timedelta(days=60))
        self.make_rows(timedelta(minutes=5))
        removed = retention.purge_expired(self.now)
        self.assertEqual(sum(removed.values()), 7)
        self.assertEqual(self.counts(), {name: 1 for name in self.counts()})
        self.assertEqual(LoginSession.objects.count(), 1)

    def test_rows_still_inside_their_grace_period_are_kept(self):
        """Expired but recent enough that something may still read them (replay markers, throttle windows, sessions)."""
        self.make_rows(timedelta(hours=2))
        self.assertEqual(sum(retention.purge_expired(self.now).values()), 0)
        self.assertEqual(LoginSession.objects.count(), 1)

    def test_a_revoked_session_is_kept_for_a_month_then_removed(self):
        recent = self.session(revoked_at=self.now - timedelta(days=3))
        old = self.session(revoked_at=self.now - timedelta(days=45))
        active = self.session()
        retention.purge_expired(self.now)
        self.assertEqual(set(LoginSession.objects.values_list("pk", flat=True)), {recent.pk, active.pk})
        self.assertFalse(LoginSession.objects.filter(pk=old.pk).exists())

    def test_accounts_events_and_deliveries_are_never_touched(self):
        event = SecurityEvent.objects.create(kind="login.failed", occurred_at=self.now - timedelta(days=900))
        AuditDelivery.objects.create(event=event, delivered_at=self.now - timedelta(days=800))
        self.make_rows(timedelta(days=900))
        retention.purge_expired(self.now)
        self.assertTrue(Account.objects.filter(pk=self.account.pk).exists())
        self.assertTrue(SecurityEvent.objects.filter(pk=event.pk).exists())
        self.assertTrue(AuditDelivery.objects.filter(pk=event.pk).exists())

    def test_one_run_removes_at_most_one_batch_per_table(self):
        for _ in range(5):
            LoginThrottle.objects.create(key=self.digest(), window_started_at=self.now - timedelta(days=3))
        self.assertEqual(retention.purge_expired(self.now, batch=2)["login_throttle"], 2)
        self.assertEqual(LoginThrottle.objects.count(), 3)
        for bad in (0, -1, 10_001, "5", None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                retention.purge_expired(self.now, batch=bad)

    def test_expired_markers_do_not_weaken_replay_detection_for_live_sessions(self):
        """A marker is only removed after its session could no longer refresh, so a live replay is still caught."""
        password = secrets.token_urlsafe(24)
        account = Account.objects.create_user("live@example.test", password, "Live", )
        Account.objects.filter(pk=account.pk).update(is_active=True)
        factory = RequestFactory()
        post = lambda view, body: view(factory.post("/x", json.dumps(body), content_type="application/json",
                                                    REMOTE_ADDR="127.0.0.1"))
        tokens = json.loads(post(accounts.login, {"email": "live@example.test", "password": password}).content)
        post(accounts.refresh, {"refresh_token": tokens["refresh_token"]})
        retention.purge_expired(self.now)
        self.assertEqual(UsedRefreshToken.objects.count(), 1)
        self.assertEqual(post(accounts.refresh, {"refresh_token": tokens["refresh_token"]}).status_code, 401)
        self.assertEqual(SecurityEvent.objects.filter(kind="session.replay").count(), 1)

    def test_login_attempts_trigger_a_rate_limited_purge_and_a_failing_purge_never_blocks_login(self):
        LoginThrottle.objects.create(key="a" * 64, window_started_at=self.now - timedelta(days=3))
        retention._state["at"] = None
        factory = RequestFactory()
        attempt = lambda: accounts.login(factory.post("/x", json.dumps({"email": "nobody@example.test",
                                                                          "password": "wrong-password-1"}),
                                                       content_type="application/json", REMOTE_ADDR="127.0.0.1"))
        self.assertEqual(attempt().status_code, 401)
        self.assertFalse(LoginThrottle.objects.filter(key="a" * 64).exists())
        LoginThrottle.objects.create(key="b" * 64, window_started_at=self.now - timedelta(days=3))
        self.assertEqual(attempt().status_code, 401)
        self.assertTrue(LoginThrottle.objects.filter(key="b" * 64).exists(), "no second purge inside the interval")
        from django.db import DatabaseError

        retention._state["at"] = None
        with patch("service.retention.purge_expired", side_effect=DatabaseError("boom")):
            self.assertEqual(attempt().status_code, 401)

    def test_command_prints_counts_only_and_validates_its_limit(self):
        self.make_rows(timedelta(days=60))
        out = StringIO()
        call_command("purge_expired_security_rows", "--limit", "10", stdout=out)
        text = out.getvalue()
        self.assertIn("login_throttle: 1", text)
        self.assertNotIn(self.account.email, text)
        self.assertEqual(LoginThrottle.objects.count(), 0)
        for bad in ("0", "10001"):
            with self.subTest(limit=bad), self.assertRaises(CommandError):
                call_command("purge_expired_security_rows", "--limit", bad, stdout=StringIO())
