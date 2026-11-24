import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from service import security_audit
from service.models import AuditDelivery, AuditEvent


class AuditContractTests(TestCase):
    def test_every_kind_business_can_emit_is_accepted_by_the_audit_producer_list(self):
        """The two services keep separate lists; this fails the build if they drift (Audit would reject with 400)."""
        import ast
        from pathlib import Path
        events = Path(__file__).resolve().parents[2] / "audit" / "service" / "events.py"
        tree = ast.parse(events.read_text())
        accepted = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PRODUCER_KINDS":
                accepted = {key.value: ast.literal_eval(value) for key, value in zip(node.value.keys, node.value.values)
                            if isinstance(value, (ast.Set, ast.Dict))}
        self.assertTrue(security_audit.KINDS <= accepted["business"], security_audit.KINDS - accepted["business"])


class AuditDeliveryTests(TestCase):
    def setUp(self):
        from django.db import transaction
        with transaction.atomic():
            self.event = security_audit.record("business.registered", uuid4(), "business", uuid4())

    def test_evidence_requires_a_transaction_and_a_known_kind(self):
        with patch.object(security_audit, "connection", MagicMock(in_atomic_block=False)):
            with self.assertRaises(RuntimeError):
                security_audit.record("business.registered", uuid4(), "business", uuid4())
        from django.db import transaction
        with transaction.atomic(), self.assertRaises(RuntimeError):
            security_audit.record("business.unknown", uuid4(), "business", uuid4())

    def test_delivery_sends_only_ids_and_decisions_and_marks_delivered(self):
        response = MagicMock(status=201)
        response.read.return_value = b'{"status":"ok"}'
        response.__enter__.return_value = response
        with patch("service.management.commands.deliver_audit_events.signed_internal_request", return_value=response) as sent:
            call_command("deliver_audit_events")
        payload = json.loads(sent.call_args.kwargs["payload"])
        self.assertEqual(set(payload), {"id", "actor_id", "kind", "occurred_at", "subject_type", "subject_id"})
        self.assertIsNotNone(AuditDelivery.objects.get().delivered_at)

    def test_failure_retains_evidence_and_backs_off(self):
        with patch("service.management.commands.deliver_audit_events.signed_internal_request", side_effect=OSError):
            with self.assertRaises(CommandError):
                call_command("deliver_audit_events")
        delivery = AuditDelivery.objects.get()
        self.assertIsNone(delivery.delivered_at)
        self.assertEqual(delivery.attempts, 1)
        self.assertGreater(delivery.next_attempt_at, timezone.now())
        self.assertEqual(AuditEvent.objects.count(), 1)
