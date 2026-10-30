"""Django database contract tests for the outbox and inbox primitives."""
from django.test import SimpleTestCase
from service import events

class EventContractTests(SimpleTestCase):
    def test_record_requires_atomic_business_transaction(self):
        with self.assertRaises(RuntimeError):
            events.record_event("engagement.received", {})
    def test_accept_requires_atomic_transaction(self):
        with self.assertRaises(RuntimeError):
            events.accept_once("2a31e65b-fb55-4f8f-ae99-f5b67a5617cb", "accepted")
    def test_event_payload_validation_requires_transaction_first(self):
        with self.assertRaises(RuntimeError):
            events.record_event("content.created", {"sample": True})
