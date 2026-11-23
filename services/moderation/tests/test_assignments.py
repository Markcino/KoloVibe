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


class AssignmentAdministrationTests(TestCase):
    def setUp(self):
        self.admin, self.moderator, self.video = uuid4(), uuid4(), uuid4()
        self.report = Report.objects.create(id=uuid4(), video_id=self.video, reporter_id=uuid4(), reason="spam")

    def call(self, operation, data, role="administrator", mfa=True, actor=None):
        request = RequestFactory().post("/internal/moderation/" + operation, {
            "actor_id": str(actor or self.admin), "role": role, "mfa_verified": mfa, "data": data},
            content_type="application/json")
        request.service_caller = "gateway"
        return moderation_workflow(request, operation)

    def grant(self, active=True, scope="reports", target=None, moderator=None):
        return self.call("assignment_set", {"scope": scope, "target_id": str(target or self.report.id),
                                            "moderator_id": str(moderator or self.moderator), "active": active})

    def test_grant_is_idempotent_audited_and_makes_the_item_visible(self):
        for _ in range(2):
            response = self.grant()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content)["active"], True)
        self.assertEqual(ModeratorAssignment.objects.filter(moderator_id=self.moderator, active=True).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.assignment_changed", actor_id=self.admin,
                                                   subject_id=self.moderator).count(), 1)
        listing = json.loads(self.call("assignment_list", {"scope": "reports", "target_id": str(self.report.id)}).content)
        self.assertEqual(listing["items"], [{"moderator_id": str(self.moderator)}])
        page = json.loads(self.call("reports", {"cursor": None}, role="moderator", actor=self.moderator).content)
        self.assertEqual([row["id"] for row in page["items"]], [str(self.report.id)])

    def test_revocation_takes_effect_and_is_audited_once(self):
        self.grant()
        for _ in range(2):
            self.assertEqual(self.grant(active=False).status_code, 200)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.assignment_changed").count(), 2)
        self.assertEqual(self.call("reports", {"cursor": None}, role="moderator", actor=self.moderator).status_code, 403)
        self.assertEqual(json.loads(self.call("assignment_list", {"scope": "reports", "target_id": str(self.report.id)}).content)["items"], [])
        # Revoking a grant that never existed changes nothing and records nothing.
        self.assertEqual(self.grant(active=False, moderator=uuid4()).status_code, 200)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.assignment_changed").count(), 2)
        self.assertEqual(ModeratorAssignment.objects.count(), 1)

    def test_only_mfa_verified_administrators_may_manage_grants(self):
        data = {"scope": "reports", "target_id": str(self.report.id), "moderator_id": str(self.moderator), "active": True}
        for role in ("moderator", "viewer", "creator"):
            self.assertEqual(self.call("assignment_set", data, role=role).status_code, 403)
            self.assertEqual(self.call("assignment_list", {"scope": "reports", "target_id": str(self.report.id)}, role=role).status_code, 403)
        self.assertEqual(self.call("assignment_set", data, mfa=False).status_code, 403)
        self.assertFalse(ModeratorAssignment.objects.exists())

    def test_invalid_and_unknown_resources_are_rejected_without_writes(self):
        for bad in ({"scope": "users"}, {"target_id": "not-a-uuid"}, {"moderator_id": str(self.admin)},
                    {"moderator_id": str(self.moderator).upper()}, {"active": "true"}, {"active": 1}):
            data = {"scope": "reports", "target_id": str(self.report.id), "moderator_id": str(self.moderator), "active": True, **bad}
            self.assertEqual(self.call("assignment_set", data).status_code, 400, bad)
        self.assertEqual(self.grant(target=uuid4()).status_code, 404)
        self.assertEqual(self.call("assignment_set", {"scope": "reports"}).status_code, 400)
        self.assertFalse(ModeratorAssignment.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(kind="moderation.assignment_changed").exists())

    @patch("service.workflow._content")
    def test_video_grants_require_existing_content(self, content):
        content.return_value = None
        self.assertEqual(self.grant(scope="videos", target=self.video).status_code, 404)
        content.return_value = {"id": str(self.video)}
        self.assertEqual(self.grant(scope="videos", target=self.video).status_code, 200)
        self.assertEqual(content.call_args.args, ("detail", {"video_id": str(self.video)}))
        self.assertTrue(ModeratorAssignment.objects.filter(queue_scope="videos", target_id=self.video, active=True).exists())


class AssignmentSummaryTests(TestCase):
    setUp = AssignmentAdministrationTests.setUp
    call = AssignmentAdministrationTests.call

    def summary(self, ids, **kwargs):
        return self.call("assignment_summary", {"moderator_ids": [str(item) for item in ids]}, **kwargs)

    def test_counts_active_grants_per_scope_and_answers_every_requested_moderator(self):
        busy, idle, other = uuid4(), uuid4(), uuid4()
        appeal_report = Report.objects.create(id=uuid4(), video_id=uuid4(), reporter_id=uuid4(), reason="spam")
        for moderator, scope, target, active in ((busy, "reports", self.report.id, True), (busy, "reports", appeal_report.id, True),
                                                  (busy, "videos", uuid4(), True), (busy, "appeals", uuid4(), False),
                                                  (other, "reports", self.report.id, True)):
            ModeratorAssignment.objects.create(moderator_id=moderator, queue_scope=scope, target_id=target, active=active)
        rows = json.loads(self.summary([busy, idle]).content)["items"]
        self.assertEqual(rows, sorted([{"moderator_id": str(busy), "videos": 1, "reports": 2, "appeals": 0},
                                       {"moderator_id": str(idle), "videos": 0, "reports": 0, "appeals": 0}],
                                      key=lambda row: row["moderator_id"]))

    def test_summary_is_administrator_mfa_only_and_strictly_bounded(self):
        mod = uuid4()
        for role in ("moderator", "viewer"):
            self.assertEqual(self.summary([mod], role=role).status_code, 403)
        self.assertEqual(self.summary([mod], mfa=False).status_code, 403)
        for bad in ([], [mod, mod], [str(mod).upper()], ["x"], [uuid4() for _ in range(51)]):
            response = self.call("assignment_summary", {"moderator_ids": [str(i).lower() if not isinstance(i, str) else i for i in bad]})
            self.assertEqual(response.status_code, 400, bad)
        self.assertEqual(self.call("assignment_summary", {"moderator_ids": "x"}).status_code, 400)
