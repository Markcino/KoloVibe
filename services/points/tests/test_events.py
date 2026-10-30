"""Django database contract tests for the outbox and inbox primitives."""
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from service import events
from django.db import transaction

class EventContractTests(SimpleTestCase):
    def test_record_requires_atomic_business_transaction(self):
        with self.assertRaises(RuntimeError):
            events.record_event("engagement.received", {})
    def test_accept_requires_atomic_transaction(self):
        with self.assertRaises(RuntimeError):
            events.accept_once("2a31e65b-fb55-4f8f-ae99-f5b67a5617cb", "accepted")
    def test_dispatch_without_pending_event_does_not_publish(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        manager = MagicMock()
        manager.__enter__.return_value = cursor
        with patch.object(events, "transaction") as tx:\n            atomic = tx.atomic
            atomic.return_value.__enter__.return_value = None
            with patch.object(events.connection, "cursor", return_value=manager):
                app = MagicMock()
                self.assertFalse(events.dispatch_one(app))
                app.send_task.assert_not_called()
