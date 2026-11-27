"""Mandate 3.4: Audit is Identity's erasure recovery source after a restore; only Identity reads it."""
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import erasure_recovery
from service.erasure_recovery import erasure_recovery as view
from service.models import SecurityEvent


class ErasureRecoveryTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.erased, self.deactivated, self.other = uuid4(), uuid4(), uuid4()

        def event(actor, kind, minutes, producer="identity"):
            return SecurityEvent.objects.create(actor_id=actor, kind=kind, producer=producer,
                                                occurred_at=self.now - timedelta(minutes=minutes),
                                                payload_digest="private")
        event(self.erased, "account.deactivated", 30)
        event(self.erased, "account.privacy_erasure_completed", 20)
        event(self.deactivated, "account.deactivated", 10)
        event(self.other, "login.succeeded", 5)
        event(self.other, "account.deactivated", 4, producer="moderation")  # never another producer's word

    def call(self, body=None, caller="identity"):
        request = RequestFactory().post("/internal/audit/erasure-recovery", body if body is not None else {},
                                        content_type="application/json")
        request.service_caller = caller
        return view(request)

    def test_identity_reads_only_deactivations_and_completed_erasures_oldest_first(self):
        response = self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        page = json.loads(response.content)
        self.assertIsNone(page["next_cursor"])
        self.assertEqual([(item["account_id"], item["kind"]) for item in page["items"]], [
            (str(self.erased), "account.deactivated"), (str(self.erased), "account.privacy_erasure_completed"),
            (str(self.deactivated), "account.deactivated")])
        self.assertEqual(set(page["items"][0]), {"id", "account_id", "kind", "occurred_at"})
        self.assertNotIn("private", response.content.decode())
        self.assertEqual(SecurityEvent.objects.filter(kind="audit.erasure_recovery_read").count(), 1)

    def test_pages_follow_the_cursor(self):
        with patch.object(erasure_recovery, "PAGE", 2):
            first = json.loads(self.call().content)
            self.assertEqual(len(first["items"]), 2)
            second = json.loads(self.call({"cursor": first["next_cursor"]}).content)
        self.assertEqual([item["account_id"] for item in second["items"]], [str(self.deactivated)])
        self.assertIsNone(second["next_cursor"])

    def test_every_other_caller_is_refused_and_bad_bodies_rejected(self):
        for caller in ("gateway", "content", None):
            self.assertEqual(self.call(caller=caller).status_code, 403, caller)
        for body in ({"cursor": "nope"}, {"cursor": str(uuid4())}, {"kind": "login.succeeded"}, []):
            self.assertEqual(self.call(body).status_code, 400, body)
        self.assertFalse(SecurityEvent.objects.filter(kind="audit.erasure_recovery_read").exists())
