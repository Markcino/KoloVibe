import json
from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase, RequestFactory
from service.models import ModeratorAssignment, Report, AuditEvent, ModerationAction
from service.workflow import moderation_workflow


class AssignmentTests(TestCase):
    def setUp(self):
        self.actor, self.other, self.video = uuid4(), uuid4(), uuid4()
        self.report = Report.objects.create(id=uuid4(), video_id=self.video, reporter_id=uuid4(), reason="spam")
        self.unassigned = Report.objects.create(id=uuid4(), video_id=uuid4(), reporter_id=uuid4(), reason="spam")

    def call(self, operation, data, role="moderator", mfa=True):
        request = RequestFactory().post("/internal/moderation/" + operation, {
            "actor_id": str(self.actor), "role": role, "mfa_verified": mfa, "data": data}, content_type="application/json")
        request.service_caller = "gateway"
        return moderation_workflow(request, operation)

    def test_unassigned_and_inactive_grants_are_denied_and_audited(self):
        for active in (None, False):
            if active is False:
                ModeratorAssignment.objects.create(moderator_id=self.actor, queue_scope="reports", target_id=self.report.id, active=False)
            self.assertEqual(self.call("reports", {"cursor": None}).status_code, 403)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.assignment_denied", actor_id=self.actor).count(), 2)

    def test_reports_are_scoped_to_actor_and_active_grant(self):
        ModeratorAssignment.objects.create(moderator_id=self.actor, queue_scope="reports", target_id=self.report.id)
        ModeratorAssignment.objects.create(moderator_id=self.other, queue_scope="reports", target_id=self.unassigned.id)
        page = json.loads(self.call("reports", {"cursor": None}).content)
        self.assertEqual([row["id"] for row in page["items"]], [str(self.report.id)])
        self.assertEqual(len(json.loads(self.call("reports", {"cursor": None}, role="administrator").content)["items"]), 2)

    def test_cross_resource_decisions_replay_and_revocation(self):
        grant = ModeratorAssignment.objects.create(moderator_id=self.actor, queue_scope="reports", target_id=self.report.id)
        data = {"target_id": str(self.unassigned.id), "action": "dismiss", "reason": "Reviewed report evidence.", "key": "assignment-test-001"}
        self.assertEqual(self.call("report_decision", data).status_code, 403)
        self.assertFalse(ModerationAction.objects.exists())
        data["target_id"] = str(self.report.id)
        for _ in range(2):
            self.assertEqual(self.call("report_decision", data).status_code, 200)
        self.assertEqual(ModerationAction.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.decision_recorded").count(), 1)
        grant.active = False
        grant.save()
        self.assertEqual(self.call("report_decision", data).status_code, 403)

    @patch("service.workflow._content")
    def test_video_scope_is_sent_only_after_mfa_and_role_checks(self, content):
        ModeratorAssignment.objects.create(moderator_id=self.actor, queue_scope="videos", target_id=self.video)
        content.return_value = {"items": [], "next_cursor": None}
        for role, mfa in (("viewer", True), ("support", True), ("moderator", False)):
            self.assertEqual(self.call("review_queue", {"cursor": None}, role=role, mfa=mfa).status_code, 403)
        content.assert_not_called()
        self.assertEqual(self.call("review_queue", {"cursor": None}).status_code, 200)
        self.assertEqual(content.call_args.args, ("queue", {"cursor": None, "scope_ids": [str(self.video)]}))
