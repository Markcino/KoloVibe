from datetime import timedelta
import io
import json
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command, CommandError
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service.models import ModeratorAssignment, Appeal, AuditDelivery, AuditEvent, ModerationAction, Report
from service.security_audit import record
from service.workflow import moderation_workflow


class Response:
    status = 201
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, limit): return b'{"status":"ok"}'[:limit]


class ModerationCompletionTests(TestCase):
    def setUp(self):
        self.actor, self.reviewer, self.video, self.creator = (uuid4() for _ in range(4))
        ModeratorAssignment.objects.create(moderator_id=self.reviewer, queue_scope="videos", target_id=self.video)
        self.snapshot = {"creator_id": str(self.creator), "state": "review", "visibility": "private", "revision": 1}
        self.content = self.enterContext(patch("service.workflow._content", side_effect=lambda op, data:
                               self.snapshot if op == "inspect" else {"applied": True}))

    def call(self, operation, data, role="creator", actor=None, mfa=False):
        request = RequestFactory().post("/internal/moderation/" + operation,
                 {"actor_id": str(actor or self.actor), "role": role, "data": data, "mfa_verified": mfa},
                 content_type="application/json")
        request.service_caller = "gateway"
        return moderation_workflow(request, operation)

    def decide(self, action="remove", **extra):
        return self.call("video_decision", {"target_id": str(self.video), "action": action,
            "reason": "Reviewed policy evidence", "reason_code": "POLICY_HARMFUL", "key": "completion-decision-001", **extra},
            role="moderator", actor=self.reviewer, mfa=True)

    def test_reviewer_queues_and_decisions_require_role_and_exact_mfa(self):
        decision = {"target_id": str(self.video), "action": "reject", "reason": "Reviewed policy concern", "key": "completion-decision-001"}
        for operation, data in (("review_queue", {"cursor": None}), ("reports", {"cursor": None}),
                                ("appeals", {"cursor": None}), ("video_decision", decision)):
            for role, mfa in (("creator", True), ("moderator", False), ("administrator", 1)):
                self.assertEqual(self.call(operation, data, role=role, mfa=mfa).status_code, 403)
        self.content.assert_not_called()
        self.assertFalse(ModerationAction.objects.exists())

    def test_notice_is_owner_only_and_tracks_latest_decision_and_own_appeal(self):
        data = {"video_id": str(self.video), "creator_id": str(self.creator)}
        self.assertEqual(json.loads(self.call("notice", data).content)["decision"], "none")
        self.assertEqual(self.call("notice", data | {"creator_id": str(uuid4())}).status_code, 404)
        self.assertEqual(self.call("notice", data, role="viewer").status_code, 403)
        self.assertEqual(self.decide().status_code, 200)
        self.snapshot.update(state="removed", revision=2)
        notice = json.loads(self.call("notice", data).content)
        self.assertEqual((notice["decision"], notice["reason_code"], notice["appealable"]), ("removed", "POLICY_HARMFUL", True))
        action = ModerationAction.objects.get()
        self.assertEqual((action.reviewer_id, action.creator_id), (self.reviewer, self.creator))
        Appeal.objects.create(removal=action, appellant_id=self.actor, reason="Original rights evidence")
        notice = json.loads(self.call("notice", data).content)
        self.assertFalse(notice["appealable"])
        self.assertEqual(notice["appeal"]["status"], "open")
        other = json.loads(self.call("notice", data, actor=uuid4()).content)
        self.assertIsNone(other["appeal"])
        ModerationAction.objects.create(id=uuid4(), video_id=self.video, reviewer_id=uuid4(), creator_id=self.creator,
              action="restore", reason="Independent reviewed evidence", reason_code="RIGHTS_CONFIRMED", status="applied",
              revision=2, finished_at=timezone.now() + timedelta(seconds=1))
        self.assertEqual(json.loads(self.call("notice", data).content)["decision"], "restored")

    def test_duplicate_open_report_code_and_transactional_audit_idempotency(self):
        self.snapshot.update(state="published", visibility="public")
        data = {"video_id": str(self.video), "reason": "spam", "details": "", "key": "completion-report-001"}
        self.assertEqual(self.call("report", data).status_code, 201)
        self.assertEqual(self.call("report", data).status_code, 200)
        duplicate = self.call("report", data | {"key": "completion-report-002"})
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(json.loads(duplicate.content)["code"], "already_reported")
        self.content.reset_mock()
        self.snapshot.update(state="removed", visibility="private")
        self.assertEqual(self.call("report", data | {"key": "completion-report-003"}).status_code, 409)
        self.content.assert_not_called()
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.report_created").count(), 1)
        self.assertEqual(self.decide().status_code, 200)
        self.assertEqual(self.decide().status_code, 200)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.decision_recorded").count(), 1)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.decision_applied").count(), 1)
        self.assertEqual(AuditEvent.objects.count(), AuditDelivery.objects.count())

    def test_audit_failure_rolls_back_business_and_guard_rejects_mutation(self):
        self.snapshot.update(state="published", visibility="public")
        with patch("service.security_audit.AuditDelivery.objects.create", side_effect=DatabaseError):
            response = self.call("report", {"video_id": str(self.video), "reason": "spam", "details": "", "key": "completion-report-001"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Report.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        with transaction.atomic(): record("moderation.report_created", self.actor, "report", uuid4())
        for sql in ("UPDATE moderation_audit_event SET kind='changed'", "DELETE FROM moderation_audit_event"):
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)

    def test_delivery_timeout_retains_evidence_and_backoff_then_acknowledges_once(self):
        with transaction.atomic(): event = record("moderation.report_created", self.actor, "report", uuid4())
        with patch("service.management.commands.deliver_audit_events.signed_internal_request", side_effect=OSError) as peer:
            with self.assertRaises(CommandError): call_command("deliver_audit_events", limit=1, stdout=io.StringIO())
            delivery = AuditDelivery.objects.get()
            self.assertEqual(delivery.attempts, 1)
            self.assertIsNone(delivery.delivered_at)
            self.assertGreater(delivery.next_attempt_at, timezone.now())
            call_command("deliver_audit_events", stdout=io.StringIO())
            self.assertEqual(peer.call_count, 1)
        AuditDelivery.objects.update(next_attempt_at=timezone.now())
        with patch("service.management.commands.deliver_audit_events.signed_internal_request", return_value=Response()) as peer:
            call_command("deliver_audit_events", limit=1, stdout=io.StringIO())
            payload = json.loads(peer.call_args.kwargs["payload"])
            self.assertEqual((payload["id"], payload["subject_type"]), (str(event.id), "report"))
            self.assertEqual(peer.call_args.kwargs["timeout"], 2)
            call_command("deliver_audit_events", stdout=io.StringIO())
            self.assertEqual(peer.call_count, 1)
        self.assertIsNotNone(AuditDelivery.objects.get().delivered_at)
        for limit in (0, 1001):
            with self.assertRaises(CommandError): call_command("deliver_audit_events", limit=limit)

    def test_standing_excludes_foreign_and_superseded_decisions(self):
        self.assertEqual(self.decide().status_code, 200)
        self.snapshot.update(state="removed", revision=2)
        data = {"creator_id": str(self.creator)}
        response = self.call("standing", data)
        self.assertEqual(len(json.loads(response.content)["notices"]), 1)
        self.assertEqual(json.loads(self.call("standing", {"creator_id": str(uuid4())}).content)["notices"], [])
        ModerationAction.objects.create(id=uuid4(), video_id=self.video, reviewer_id=uuid4(), creator_id=self.creator,
                action="publish", reason="Reviewed again", status="applied", finished_at=timezone.now() + timedelta(seconds=1))
        self.assertEqual(json.loads(self.call("standing", data).content)["notices"], [])

    def test_legacy_owner_lookup_is_bounded_and_backfill_uses_content(self):
        for _ in range(21):
            ModerationAction.objects.create(id=uuid4(), video_id=uuid4(), reviewer_id=self.reviewer,
                    action="reject", reason="Historical decision", status="applied")
        self.assertEqual(self.call("standing", {"creator_id": str(self.creator)}).status_code, 503)
        self.content.assert_not_called()
        call_command("backfill_action_owners", limit=5, stdout=io.StringIO())
        self.assertEqual(ModerationAction.objects.filter(creator_id=self.creator).count(), 5)

    def test_conflicted_decision_is_audited_and_never_appears_as_applied_notice(self):
        self.content.side_effect = lambda operation, data: self.snapshot if operation == "inspect" else None
        self.assertEqual(self.decide().status_code, 409)
        self.assertEqual(ModerationAction.objects.get().status, "conflict")
        self.assertEqual(set(AuditEvent.objects.values_list("kind", flat=True)),
                         {"moderation.decision_recorded", "moderation.decision_conflicted"})
        self.assertTrue(all(event.actor_id == self.reviewer for event in AuditEvent.objects.all()))
        result = self.call("notice", {"video_id": str(self.video), "creator_id": str(self.creator)})
        self.assertEqual(json.loads(result.content)["decision"], "none")

    def test_notice_restriction_requires_real_applied_action(self):
        ModerationAction.objects.create(id=uuid4(), video_id=self.video, reviewer_id=self.reviewer,
                creator_id=self.creator, action="restrict", status="applied", reason="Recorded restriction evidence",
                reason_code="POLICY_RESTRICTED", finished_at=timezone.now())
        result = self.call("notice", {"video_id": str(self.video), "creator_id": str(self.creator)})
        notice = json.loads(result.content)
        self.assertEqual((notice["decision"], notice["reason_code"], notice["appealable"]),
                         ("restricted", "POLICY_RESTRICTED", False))
