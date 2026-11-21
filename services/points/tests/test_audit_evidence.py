"""Ledger decisions must leave immutable, atomically recorded, retryable audit evidence."""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import io
import json
from unittest.mock import patch
from uuid import UUID, uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from service import security_audit
from service.models import AuditDelivery, AuditEvent, DailyAwardCount, PointsEntry, QualificationReceipt
from service.pilot_points import apply_qualified_view

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def apply(event_id, account):
    return apply_qualified_view(event_id, {"creator_user_id": str(account), "qualified_at": NOW.isoformat()})


class Fixture:
    def setUp(self):
        super().setUp()
        self.account = uuid4()
        self.enterContext(patch("service.pilot_points.timezone.now", return_value=NOW))
        self.enterContext(patch("service.pilot_points.accept_once", side_effect=self.accept))
        self.seen = set()

    def accept(self, event, _):
        if event in self.seen:
            return False
        self.seen.add(event)
        return True


class LedgerEvidenceTests(Fixture, TestCase):
    def test_award_records_one_event_and_delivery_for_the_entry(self):
        event = uuid4()
        self.assertTrue(apply(event, self.account))
        evidence = AuditEvent.objects.get()
        self.assertEqual((evidence.kind, evidence.subject_type, evidence.subject_id),
                         ("points.awarded", "points_entry", event))
        self.assertTrue(PointsEntry.objects.filter(entry_id=event).exists())
        self.assertEqual(AuditDelivery.objects.get().event_id, evidence.id)
        self.assertIsNone(AuditDelivery.objects.get().delivered_at)

    def test_duplicate_redelivery_adds_no_evidence(self):
        event = uuid4()
        self.assertTrue(apply(event, self.account))
        self.assertFalse(apply(event, self.account))
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_daily_cap_withholding_is_recorded_once_without_a_ledger_entry(self):
        DailyAwardCount.objects.create(creator_user_id=self.account, day=NOW.date(), awards=100)
        event = uuid4()
        self.assertFalse(apply(event, self.account))
        self.assertFalse(apply(event, self.account))
        evidence = AuditEvent.objects.get()
        self.assertEqual((evidence.kind, evidence.subject_id), ("points.withheld", event))
        self.assertFalse(PointsEntry.objects.exists())
        self.assertEqual(QualificationReceipt.objects.get(pk=event).status, "withheld")

    def test_invalid_payload_records_nothing(self):
        with self.assertRaises(ValueError):
            apply_qualified_view(uuid4(), {"creator_user_id": "bad", "qualified_at": NOW.isoformat()})
        self.assertFalse(AuditEvent.objects.exists())

    def test_evidence_carries_no_account_or_creator_identifier(self):
        apply(uuid4(), self.account)
        fields = {field.name for field in AuditEvent._meta.fields}
        self.assertEqual(fields, {"id", "kind", "actor_id", "occurred_at", "subject_type", "subject_id"})
        self.assertIsNone(AuditEvent.objects.get().actor_id)
        self.assertNotIn(str(self.account), str(AuditEvent.objects.values().get()))

    def test_audit_rows_are_append_only(self):
        apply(uuid4(), self.account)
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.update(kind="points.withheld")
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.all().delete()
        self.assertEqual(AuditEvent.objects.get().kind, "points.awarded")


class AtomicityTests(Fixture, TestCase):  # append-only triggers forbid table flushes
    def test_failed_evidence_rolls_back_the_award_and_cap_counter(self):
        event = uuid4()
        with patch("service.pilot_points.audit_record", side_effect=RuntimeError("audit down")):
            with self.assertRaises(RuntimeError):
                apply(event, self.account)
        self.assertFalse(PointsEntry.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(DailyAwardCount.objects.filter(creator_user_id=self.account).exists())
        self.assertEqual(QualificationReceipt.objects.get(pk=event).status, "pending")
        self.seen.clear()  # the broker retry resumes the pending receipt
        self.assertTrue(apply(event, self.account))
        self.assertEqual(AuditEvent.objects.count(), 1)


class RecorderContractTests(SimpleTestCase):
    def test_requires_owning_transaction_and_known_kind(self):
        with self.assertRaises(RuntimeError):
            security_audit.record("points.awarded", uuid4())
        with patch("service.security_audit.connection") as connection:
            connection.in_atomic_block = True
            for kind in ("points.reversed", "points.adjusted", "moderation.report_created", ""):
                with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                    security_audit.record(kind, uuid4())

    def test_emitted_kinds_are_within_the_audit_points_allow_list(self):
        self.assertTrue(security_audit.KINDS <= {"points.awarded", "points.withheld",
                                                 "points.reversed", "points.adjusted", "points.review_read", "points.review_denied"})


class Response:
    def __init__(self, status=201, body=b'{"status":"ok"}'):
        self.status, self.body = status, body

    def read(self, _):
        return self.body


@contextmanager
def reply(response):
    yield response


class DeliveryTests(TestCase):
    def event(self, kind="points.awarded"):
        event = AuditEvent.objects.create(kind=kind, subject_id=uuid4())
        AuditDelivery.objects.create(event=event)
        return event

    def run_command(self, *args, **kwargs):
        out = io.StringIO()
        call_command("deliver_audit_events", *args, stdout=out, **kwargs)
        return out.getvalue()

    def test_delivers_exact_signed_payload_to_the_audit_ingest_path(self):
        event = self.event()
        calls = []

        def send(audience, path, **kwargs):
            calls.append((audience, path, kwargs))
            return reply(Response())

        with patch("service.management.commands.deliver_audit_events.signed_internal_request", side_effect=send):
            self.assertIn("acknowledged", self.run_command())
        audience, path, kwargs = calls[0]
        self.assertEqual((audience, path, kwargs["method"], kwargs["timeout"]),
                         ("audit", "/internal/security-events", "POST", 2))
        payload = json.loads(kwargs["payload"])
        # Contract with the audit ingest: exact key set, null actor, paired subject.
        self.assertEqual(set(payload), {"id", "actor_id", "kind", "occurred_at", "subject_type", "subject_id"})
        self.assertEqual((payload["id"], payload["actor_id"], payload["kind"], payload["subject_type"]),
                         (str(event.id), None, "points.awarded", "points_entry"))
        self.assertEqual(UUID(payload["subject_id"]), event.subject_id)
        self.assertLess(len(kwargs["payload"]), 2048)
        self.assertIsNotNone(AuditDelivery.objects.get().delivered_at)

    def test_failure_retains_evidence_and_backs_off_then_retries(self):
        self.event()
        with patch("service.management.commands.deliver_audit_events.signed_internal_request",
                   side_effect=OSError("down")), self.assertRaises(CommandError):
            self.run_command()
        delivery = AuditDelivery.objects.get()
        self.assertEqual((delivery.attempts, delivery.delivered_at), (1, None))
        self.assertGreater(delivery.next_attempt_at, timezone.now())
        self.assertEqual(AuditEvent.objects.count(), 1)
        with patch("service.management.commands.deliver_audit_events.signed_internal_request") as send:
            self.run_command()
            send.assert_not_called()  # not due yet
        AuditDelivery.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        with patch("service.management.commands.deliver_audit_events.signed_internal_request",
                   side_effect=lambda *a, **k: reply(Response(200))):
            self.run_command()
        self.assertIsNotNone(AuditDelivery.objects.get().delivered_at)

    def test_unexpected_acknowledgments_are_not_treated_as_delivery(self):
        for response in (Response(500), Response(201, b'{"status":"other"}'), Response(201, b"not json"),
                         Response(201, b"x" * 101)):
            event = self.event()
            with self.subTest(status=response.status, body=response.body[:10]), patch(
                    "service.management.commands.deliver_audit_events.signed_internal_request",
                    side_effect=lambda *a, **k: reply(response)), self.assertRaises(CommandError):
                self.run_command()
            self.assertIsNone(AuditDelivery.objects.get(event=event).delivered_at)

    def test_batch_limit_is_bounded_and_validated(self):
        for bad in (0, 1001):
            with self.assertRaises(CommandError):
                self.run_command(limit=bad)
        for _ in range(3):
            self.event()
        with patch("service.management.commands.deliver_audit_events.signed_internal_request",
                   side_effect=lambda *a, **k: reply(Response())) as send:
            self.run_command(limit=2)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(AuditDelivery.objects.filter(delivered_at__isnull=True).count(), 1)
