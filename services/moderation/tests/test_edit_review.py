"""Decision A (RV2-01): reviewer queue, detail and decisions for held edits to published videos."""

import json
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.models import AuditEvent, EditDecision, ModeratorAssignment
from service.workflow import moderation_workflow
from service.edit_review import valid_content

KEY = "edit-decision-key-0001"
REASON = "Title matches the video and policy"


class EditReviewTests(TestCase):
    def setUp(self):
        self.actor, self.other, self.video, self.revision = uuid4(), uuid4(), uuid4(), uuid4()
        ModeratorAssignment.objects.create(moderator_id=self.actor, queue_scope="videos", target_id=self.video)
        values = {"title": "Live", "description": "", "category": "hipco", "tags": []}
        self.detail = {"id": str(self.revision), "video_id": str(self.video), "creator_id": str(uuid4()),
                       "status": "pending", "submitted_at": "2026-11-25T12:00:00+00:00", "video_state": "published",
                       "live": values, "proposed": values | {"title": "Proposed"}}
        self.calls = []
        self.applied = True
        self.content = self.enterContext(patch("service.workflow._content", side_effect=self.answer))

    def answer(self, operation, payload):
        self.calls.append((operation, payload))
        if operation == "edits":
            return {"items": [], "next_cursor": None}
        if operation == "edit-detail":
            return dict(self.detail) if payload["revision_id"] == str(self.revision) else None
        if operation == "edit-apply":
            return {"applied": True} if self.applied else None
        raise AssertionError(operation)

    def call(self, operation, data, actor=None, role="moderator", mfa=True):
        request = RequestFactory().post("/internal/moderation/" + operation, {
            "actor_id": str(actor or self.actor), "role": role, "mfa_verified": mfa, "data": data},
            content_type="application/json")
        request.service_caller = "gateway"
        return moderation_workflow(request, operation)

    def decide(self, action="approve", key=KEY, actor=None, role="moderator", **extra):
        return self.call("edit_decision", {"target_id": str(self.revision), "action": action, "reason": REASON,
                                           "key": key, **extra}, actor=actor, role=role)

    def test_queue_is_scoped_to_assigned_videos_and_requires_mfa(self):
        self.assertEqual(self.call("edit_queue", {"cursor": None}).status_code, 200)
        self.assertEqual(self.calls[-1], ("edits", {"cursor": None, "scope_ids": [str(self.video)]}))
        self.assertEqual(self.call("edit_queue", {"cursor": None}, role="administrator", actor=self.other).status_code, 200)
        self.assertEqual(self.calls[-1], ("edits", {"cursor": None}))
        self.assertEqual(self.call("edit_queue", {"cursor": None}, actor=self.other).status_code, 403)
        self.assertEqual(self.call("edit_queue", {"cursor": None}, mfa=False).status_code, 403)
        self.assertEqual(self.call("edit_queue", {"cursor": None}, role="creator").status_code, 403)

    def test_detail_is_assignment_scoped_audited_and_hides_the_owner(self):
        response = self.call("edit_detail", {"target_id": str(self.revision)})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual((data["edit"]["proposed"]["title"], data["decisions"]), ("Proposed", []))
        self.assertNotIn("creator_id", data["edit"])
        self.assertTrue(AuditEvent.objects.filter(kind="moderation.reviewer_read", actor_id=self.actor).exists())
        self.assertEqual(self.call("edit_detail", {"target_id": str(self.revision)}, actor=self.other).status_code, 403)
        self.assertEqual(self.call("edit_detail", {"target_id": str(uuid4())}).status_code, 404)

    def test_decision_is_recorded_applied_and_replayed_with_the_same_key(self):
        response = self.decide()
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual((result["action"], result["status"], result["video_id"]), ("approve", "applied", str(self.video)))
        decision = EditDecision.objects.get()
        self.assertEqual((decision.reason_code, decision.reviewer_id), ("REVIEWED_EDIT_APPROVE", self.actor))
        applies = [payload for operation, payload in self.calls if operation == "edit-apply"]
        self.assertEqual(applies, [{"revision_id": str(self.revision), "action_id": str(decision.id),
                                    "action": "approve", "reason_code": "REVIEWED_EDIT_APPROVE"}])
        self.assertEqual(self.decide().status_code, 200)  # replay answers the recorded outcome
        self.assertEqual(len([1 for operation, _ in self.calls if operation == "edit-apply"]), 1)
        self.assertEqual(self.decide(action="reject").status_code, 409)  # the key names one decision
        self.assertEqual(list(AuditEvent.objects.filter(subject_id=decision.id).values_list("kind", flat=True).order_by("occurred_at")),
                         ["moderation.decision_recorded", "moderation.decision_applied"])

    def test_second_decision_on_the_same_edit_is_refused(self):
        self.assertEqual(self.decide().status_code, 200)
        self.assertEqual(self.decide(key="edit-decision-key-0002", role="administrator", actor=self.other).status_code, 409)

    def test_content_conflict_is_recorded_and_allows_a_fresh_decision(self):
        self.applied = False
        self.assertEqual(self.decide().status_code, 409)
        self.assertEqual(EditDecision.objects.get().status, "conflict")
        self.assertTrue(AuditEvent.objects.filter(kind="moderation.decision_conflicted").exists())
        self.applied = True
        self.assertEqual(self.decide(key="edit-decision-key-0003").status_code, 200)

    def test_decided_or_unassigned_edits_and_bad_input_are_refused(self):
        self.assertEqual(self.decide(actor=self.other).status_code, 403)
        self.detail["status"] = "superseded"
        self.assertEqual(self.decide().status_code, 409)
        self.detail["status"] = "pending"
        for bad in ({"action": "publish"}, {"key": "short"}, {"reason_code": "lower"}):
            data = {"action": "approve", "key": KEY} | bad
            self.assertEqual(self.decide(**data).status_code, 400)
        self.assertEqual(self.call("edit_decision", {"target_id": str(self.revision), "action": "approve",
                                                     "reason": "short", "key": KEY}).status_code, 400)
        self.assertFalse(EditDecision.objects.exists())

    def test_content_answers_are_checked(self):
        self.assertTrue(valid_content("edit-detail", self.detail, {"revision_id": str(self.revision)}))
        self.assertFalse(valid_content("edit-detail", self.detail, {"revision_id": str(uuid4())}))
        self.assertFalse(valid_content("edit-detail", self.detail | {"live": {"title": "x"}}, {"revision_id": str(self.revision)}))
        self.assertFalse(valid_content("edit-detail", self.detail | {"extra": 1}, {"revision_id": str(self.revision)}))
        self.assertTrue(valid_content("edits", {"items": [], "next_cursor": None}, {}))
        self.assertFalse(valid_content("edits", {"items": [], "next_cursor": "x"}, {}))
