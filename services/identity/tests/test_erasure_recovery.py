"""Mandate 3.4: after an older Identity backup is restored, the facts Audit holds are re-applied, so an erased or
deactivated account does not come back. The restored state is built directly: the backup predates the approval."""
import json
import secrets
import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from urllib.error import URLError

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from service import erasure
from service.management.commands import recover_erasures_from_audit as command
from service.models import Account, ErasureJob, LoginSession, PrivacyRequest, SecurityEvent, TotpFactor


class Response:
    def __init__(self, body, status=200):
        self.status, self.body = status, json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit):
        return self.body[:limit]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ErasureRecoveryTests(TestCase):
    def setUp(self):
        # The restored backup: the person is active, signed in, and their deletion request waits for review.
        self.person = Account.objects.create_user("person@example.test", secrets.token_urlsafe(24), "Person")
        LoginSession.objects.create(account=self.person, expires_at=timezone.now() + timedelta(days=1),
                                    refresh_digest=secrets.token_hex(32))
        TotpFactor.objects.create(account=self.person, encrypted_secret="x")
        self.request = PrivacyRequest.objects.create(account=self.person, kind="deletion", status="in_review")
        self.bystander = Account.objects.create_user("other@example.test", secrets.token_urlsafe(24), "Other")

    def facts(self, *pairs):
        return [{"id": str(uuid.uuid4()), "account_id": str(account), "kind": kind,
                 "occurred_at": timezone.now().isoformat()} for account, kind in pairs]

    def run_with(self, pages, *arguments):
        answers = iter(Response({"items": items, "next_cursor": cursor}) for items, cursor in pages)
        out = StringIO()
        with patch.object(command, "signed_internal_request", side_effect=lambda *a, **k: next(answers)) as call:
            call_command("recover_erasures_from_audit", *arguments, stdout=out)
        return out.getvalue(), call

    def outbox(self):
        with connection.cursor() as cur:
            cur.execute("SELECT payload FROM event_outbox")
            return [json.loads(row[0]) for row in cur.fetchall()]

    def test_a_completed_erasure_does_not_come_back_after_a_restore(self):
        facts = self.facts((self.person.id, "account.deactivated"),
                           (self.person.id, "account.privacy_erasure_completed"), (uuid.uuid4(), "account.deactivated"))
        out, call = self.run_with([(facts[:2], facts[1]["id"]), (facts[2:], None)])
        self.assertEqual(call.call_count, 2, "it follows the cursor to the end")
        self.assertEqual(json.loads(call.call_args_list[1].kwargs["payload"]), {"cursor": facts[1]["id"]})
        self.assertEqual(call.call_args.args[:2], ("audit", "/internal/audit/erasure-recovery"))
        self.assertIn("Re-applied 2 recorded facts (0 already in place, 1 accounts not in this database)", out)
        self.assertNotIn(str(self.person.id), out)
        person = Account.objects.get(pk=self.person.pk)
        self.assertEqual((person.email, person.display_name, person.is_active),
                         (f"erased-{person.id.hex}@invalid", "", False))
        self.assertFalse(person.has_usable_password())
        self.assertFalse(LoginSession.objects.filter(account=person).exists())
        self.assertFalse(TotpFactor.objects.filter(account=person).exists())
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "processing", "never marked completed here")
        self.assertEqual(ErasureJob.objects.filter(request=self.request).count(), 5)
        self.assertEqual(sorted(row["service"] for row in self.outbox()), ["business", "creators", "engagement"],
                         "every service is asked again, Moderation and Content after Creators")
        self.assertEqual(Account.objects.get(pk=self.bystander.pk).email, "other@example.test")
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_erasure_recovered").count(), 2)

    def test_a_deactivation_alone_signs_the_account_out_without_erasing_it(self):
        self.run_with([(self.facts((self.person.id, "account.deactivated")), None)])
        person = Account.objects.get(pk=self.person.pk)
        self.assertEqual((person.email, person.is_active), ("person@example.test", False))
        self.assertFalse(LoginSession.objects.filter(account=person, revoked_at__isnull=True).exists())

    def test_running_it_again_changes_nothing(self):
        facts = self.facts((self.person.id, "account.deactivated"),
                           (self.person.id, "account.privacy_erasure_completed"))
        self.run_with([(facts, None)])
        before = len(self.outbox())
        out, _ = self.run_with([(facts, None)])
        self.assertIn("Re-applied 0 recorded facts (2 already in place", out)
        self.assertEqual(len(self.outbox()), before)

    def test_a_dry_run_changes_nothing(self):
        facts = self.facts((self.person.id, "account.privacy_erasure_completed"))
        out, _ = self.run_with([(facts, None)], "--dry-run")
        self.assertIn("Would re-apply 1 recorded facts", out)
        person = Account.objects.get(pk=self.person.pk)
        self.assertEqual((person.email, person.is_active), ("person@example.test", True))
        self.assertEqual((self.outbox(), SecurityEvent.objects.filter(
            kind="account.privacy_erasure_recovered").count()), ([], 0))

    def test_an_unavailable_or_malformed_source_stops_with_nothing_further_changed(self):
        for failure in (URLError("down"), Response({}, 503), Response({"items": [{"kind": "login.succeeded"}],
                                                                       "next_cursor": None})):
            with self.subTest(failure=failure), patch.object(
                    command, "signed_internal_request",
                    side_effect=failure if isinstance(failure, Exception) else lambda *a, **k: failure), \
                    self.assertRaises(CommandError):
                call_command("recover_erasures_from_audit", stdout=StringIO())
        self.assertTrue(Account.objects.get(pk=self.person.pk).is_active)

    def test_recover_reports_a_missing_account(self):
        from django.db import transaction
        with transaction.atomic():
            self.assertEqual(erasure.recover(str(uuid.uuid4()), "account.deactivated"), "missing")
