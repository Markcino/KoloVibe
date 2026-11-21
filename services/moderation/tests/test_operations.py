import json
from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase, RequestFactory
from service.models import ModeratorAssignment, Report, AuditEvent
from service.workflow import moderation_workflow


class OperationTests(TestCase):
    def setUp(self):
        self.actor = uuid4()
        self.mine = Report.objects.create(id=uuid4(), video_id=uuid4(), reporter_id=uuid4(), reason="spam")
        self.other = Report.objects.create(id=uuid4(), video_id=uuid4(), reporter_id=uuid4(), reason="spam", status="resolved")

    def call(self, operation, data, role="moderator", mfa=True):
        request = RequestFactory().post("/internal/moderation/" + operation, {"actor_id": str(self.actor), "role": role,
            "mfa_verified": mfa, "data": data}, content_type="application/json")
        request.service_caller = "gateway"
        return moderation_workflow(request, operation)

    @patch("service.workflow._content")
    def test_totals_scope_status_and_audit(self, content):
        content.return_value = dict.fromkeys(["review", "published", "rejected", "removed"], 0)
        self.assertEqual(self.call("totals", {}).status_code, 403)
        ModeratorAssignment.objects.create(moderator_id=self.actor, queue_scope="reports", target_id=self.mine.id)
        scoped = json.loads(self.call("totals", {}).content)
        self.assertEqual(scoped["reports"], {"open": 1, "resolved": 0, "dismissed": 0})
        self.assertEqual(content.call_args.args, ("totals", {"scope_ids": []}))
        global_counts = json.loads(self.call("totals", {}, role="administrator").content)
        self.assertEqual(global_counts["reports"]["resolved"], 1)
        self.assertTrue(AuditEvent.objects.filter(kind="moderation.totals_read").exists())
        self.assertEqual(self.call("totals", {}, mfa=False).status_code, 403)
        self.assertEqual(self.call("totals", {}, role="viewer").status_code, 403)
        page = json.loads(self.call("reports", {"cursor": None, "status": "resolved"}).content)
        self.assertEqual(page["items"], [])
        global_page = json.loads(self.call("reports", {"cursor": None, "status": "resolved"}, role="administrator").content)
        self.assertEqual([item["id"] for item in global_page["items"]], [str(self.other.id)])
        self.assertEqual(self.call("reports", {"cursor": None, "status": "unsupported"}).status_code, 400)

    def test_fraud_scope_contains_only_videos_of_active_assignments(self):
        ModeratorAssignment.objects.create(moderator_id=self.actor, queue_scope="reports", target_id=self.mine.id)
        self.assertEqual(json.loads(self.call("fraud_scope", {}).content), {"video_ids": [str(self.mine.video_id)]})
        self.assertEqual(json.loads(self.call("fraud_scope", {}, role="administrator").content), {"video_ids": None})
