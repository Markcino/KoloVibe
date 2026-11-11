import json
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.models import Appeal, AuditDelivery, AuditEvent, ModerationAction, Report
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
            "actor_id": str(actor), "role": role, "data": data, "mfa_verified": role in {"moderator", "administrator"},
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
        event = AuditEvent.objects.get(kind="moderation.appeal_created")
        self.assertEqual((event.actor_id, event.subject_type, str(event.subject_id)),
                         (self.viewer, "appeal", json.loads(appeal.content)["id"]))
        self.assertEqual(AuditEvent.objects.count(), AuditDelivery.objects.count())
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

    def test_report_status_reads_are_owner_scoped_and_paginated(self):
        foreign = Report.objects.create(id=uuid4(), video_id=uuid4(), reporter_id=uuid4(),
                                        reason="spam", details="Private report details")
        owned = [Report.objects.create(id=uuid4(), video_id=uuid4(), reporter_id=self.viewer,
                                       reason="spam", details="My report details") for _ in range(21)]
        first = self.call("own_reports", self.viewer, "viewer", {"cursor": None})
        self.assertEqual(first.status_code, 200)
        page = json.loads(first.content)
        self.assertEqual(len(page["items"]), 20)
        self.assertIsNotNone(page["next_cursor"])
        second = self.call("own_reports", self.viewer, "viewer", {"cursor": page["next_cursor"]})
        self.assertEqual(len(json.loads(second.content)["items"]), 1)
        self.assertEqual(json.loads(second.content)["next_cursor"], None)
        self.assertEqual(self.call("own_report", self.viewer, "viewer",
                                   {"target_id": str(foreign.id)}).status_code, 404)
        self.assertEqual(self.call("own_report", self.viewer, "viewer",
                                   {"target_id": str(owned[0].id)}).status_code, 200)
        self.assertEqual(self.call("own_reports", self.viewer, "viewer",
                                   {"cursor": "invalid"}).status_code, 400)
        self.assertEqual(self.call("own_reports", self.viewer, "viewer",
                                   {"cursor": None}, caller="content").status_code, 403)

    def test_appeal_status_reads_hide_other_accounts_records(self):
        removal = ModerationAction.objects.create(id=uuid4(), video_id=uuid4(), reviewer_id=self.reviewer,
                                                  action="remove", reason="Removed after review",
                                                  revision=1, status="applied")
        foreign = Appeal.objects.create(removal=removal, appellant_id=uuid4(), reason="Private appeal")
        self.assertEqual(self.call("own_appeal", self.viewer, "viewer",
                                   {"target_id": str(foreign.id)}).status_code, 404)
        self.assertEqual(json.loads(self.call("own_appeals", self.viewer, "viewer",
                                              {"cursor": None}).content)["items"], [])
        self.assertEqual(self.call("own_appeal", foreign.appellant_id, "creator",
                                   {"target_id": str(foreign.id)}).status_code, 200)
        self.assertEqual(self.call("own_appeals", self.reviewer, "moderator",
                                   {"cursor": None}).status_code, 403)
