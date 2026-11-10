import json
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.models import Appeal, ModerationAction, Report
from service.workflow import ContentUnavailable, moderation_workflow


class PilotModerationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.video = str(uuid4())
        self.creator = str(uuid4())
        self.viewer = uuid4()
        self.reviewer = uuid4()
        self.independent = uuid4()

    def call(self, operation, actor, role, data, caller="gateway"):
        request = self.factory.post("/internal/moderation/" + operation, {
            "actor_id": str(actor), "role": role, "data": data,
        }, content_type="application/json")
        request.service_caller = caller
        return moderation_workflow(request, operation)

    @patch("service.workflow._content")
    def test_report_removal_and_appeal_require_independent_reviewer(self, content):
        snapshot = {"state": "published", "visibility": "public", "creator_id": self.creator, "revision": 1}
        content.side_effect = lambda op, data: snapshot if op == "inspect" else {"applied": True}
        report = {"video_id": self.video, "reason": "copyright", "details": "A pilot rights concern.",
                  "key": "test-report-key-001"}
        first = self.call("report", self.viewer, "viewer", report)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.call("report", self.viewer, "viewer", report).status_code, 200)
        self.assertEqual(self.call("report", self.viewer, "viewer",
                                   report | {"key": "different-report-001"}).status_code, 409)
        decision = {"target_id": json.loads(first.content)["id"], "action": "remove",
                    "reason": "Recorded rights concern.", "key": "test-remove-key-001"}
        self.assertEqual(self.call("report_decision", self.viewer, "viewer", decision).status_code, 403)
        self.assertEqual(self.call("report_decision", self.reviewer, "moderator", decision).status_code, 200)
        self.assertEqual(Report.objects.get().status, "resolved")
        snapshot.update(state="removed", visibility="private", revision=2)
        appeal_data = {"video_id": self.video, "creator_id": self.creator, "reason": "Rights evidence provided."}
        self.assertEqual(self.call("appeal", self.viewer, "viewer",
                                   appeal_data | {"creator_id": str(uuid4())}).status_code, 404)
        appeal = self.call("appeal", self.viewer, "viewer", appeal_data)
        self.assertEqual(appeal.status_code, 201)
        restoration = {"target_id": json.loads(appeal.content)["id"], "action": "restore",
                       "reason": "Rights confirmed by second reviewer.", "key": "test-restore-key-001"}
        self.assertEqual(self.call("appeal_decision", self.reviewer, "moderator", restoration).status_code, 403)
        self.assertEqual(self.call("appeal_decision", self.independent, "administrator", restoration).status_code, 200)
        self.assertEqual(Appeal.objects.get().status, "restored")
        self.assertEqual(ModerationAction.objects.filter(status="applied").count(), 2)

    @patch("service.workflow._content")
    def test_lost_result_preserves_pending_decision_for_same_key_retry(self, content):
        decision = {"target_id": self.video, "action": "publish", "reason": "Content review complete.",
                    "key": "test-publish-key-001"}
        content.side_effect = [
            {"state": "review", "visibility": "private", "creator_id": self.creator, "revision": 0},
            ContentUnavailable, {"applied": True},
        ]
        self.assertEqual(self.call("video_decision", self.reviewer, "moderator", decision).status_code, 503)
        self.assertEqual(ModerationAction.objects.get().status, "pending")
        self.assertEqual(self.call("video_decision", self.reviewer, "moderator", decision).status_code, 200)
        self.assertEqual(self.call("video_decision", self.reviewer, "moderator", decision).status_code, 200)
        self.assertEqual(content.call_args_list[1], content.call_args_list[2])
        self.assertEqual(ModerationAction.objects.get().status, "applied")
