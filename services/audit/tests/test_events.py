import json
import uuid

from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service.events import ingest
from service.models import SecurityEvent


class SecurityEventTests(TestCase):
    def test_identity_settings_security_kinds_are_accepted_idempotently(self):
        for kind in ("account.preferences_updated", "account.privacy_request_received",
                     "account.reauthenticated", "account.reauthentication_failed",
                     "account.reauthentication_throttled", "session.listed"):
            payload = {**self.payload, "id": str(uuid.uuid4()), "kind": kind}
            self.assertEqual(self.send(payload).status_code, 201)
            self.assertEqual(self.send(payload).status_code, 200)

    def setUp(self):
        self.factory = RequestFactory()
        self.payload = {"id": str(uuid.uuid4()), "actor_id": str(uuid.uuid4()),
                        "kind": "mfa.succeeded", "occurred_at": timezone.now().isoformat()}

    def send(self, payload=None, caller="identity"):
        request = self.factory.post("/internal/security-events", json.dumps(payload or self.payload),
                                    content_type="application/json")
        request.service_caller = caller
        return ingest(request)

    def test_idempotent_ingestion_and_conflicting_identity(self):
        self.assertEqual(self.send().status_code, 201)
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(SecurityEvent.objects.count(), 1)
        self.assertEqual(self.send(dict(self.payload, kind="mfa.failed")).status_code, 409)

    def test_unauthorized_caller_and_secret_bearing_payload_fail(self):
        self.assertEqual(self.send(caller="gateway").status_code, 403)
        self.assertEqual(self.send(dict(self.payload, credential="never-allowed")).status_code, 400)
        for field in ("id", "actor_id", "kind", "occurred_at"):
            self.assertEqual(self.send(dict(self.payload, **{field: []})).status_code, 400)
        self.assertFalse(SecurityEvent.objects.exists())

    def test_database_guards_reject_mutation(self):
        self.send()
        for operation in (lambda: SecurityEvent.objects.all().update(kind="mfa.failed"),
                          lambda: SecurityEvent.objects.all().delete()):
            with self.assertRaises(DatabaseError), transaction.atomic():
                operation()
