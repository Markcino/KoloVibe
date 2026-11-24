"""The audit page contract must accept every producer Audit can hold, and nothing else.

A producer missing here makes every event from that service fail the page with a 503 (the Business producer was).
"""
from uuid import uuid4

from django.test import SimpleTestCase

from service.admin_contracts import valid_audit_page
from service.responses import error_response  # noqa: F401  (import guards against the module moving)

PRODUCERS = ("identity", "moderation", "creators", "content", "points", "audit", "business")


def page(producer, kind="business.verification_decided", subject="business"):
    return {"items": [{"id": str(uuid4()), "kind": kind, "occurred_at": "2026-11-24T10:00:00+00:00",
                       "producer": producer, "subject_type": subject}], "next_cursor": None}


class AuditContractTests(SimpleTestCase):
    def test_every_audit_producer_is_accepted_including_business(self):
        for producer in PRODUCERS:
            self.assertTrue(valid_audit_page(page(producer)), producer)

    def test_an_unknown_producer_or_extra_field_is_refused(self):
        self.assertFalse(valid_audit_page(page("billing")))
        extra = page("business")
        extra["items"][0]["actor_id"] = str(uuid4())
        self.assertFalse(valid_audit_page(extra))
        self.assertFalse(valid_audit_page(page("business", kind="x" * 65)))

    def test_the_console_copy_agrees(self):
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parents[3] / "apps" / "web_django" / "web" / "admin_contracts.py"
        spec = importlib.util.spec_from_file_location("console_admin_contracts", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for producer in PRODUCERS:
            self.assertTrue(module.valid_audit_page(page(producer)), producer)
        self.assertFalse(module.valid_audit_page(page("billing")))
