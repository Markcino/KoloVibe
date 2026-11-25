"""Decision A (RV2-01): the Gateway side of reviewed edits to published videos."""

import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service import media
from service.moderation import _valid_result, moderation_endpoint
from service.reviewer_contracts import valid_edit_detail
from service.video_validation import valid_edit_review, valid_video
from .test_accounts import Response
from .video_fixtures import metadata

VALUES = {"title": "Live", "description": "", "category": "hipco", "tags": []}


def pending(**proposed):
    return {"id": str(uuid4()), "status": "pending", "submitted_at": "2026-11-25T12:00:00+00:00",
            "decided_at": None, "reason_code": None, "proposed": VALUES | proposed}


class EditReviewGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.creator, self.video = str(uuid4()), str(uuid4())

    def item(self, **changes):
        return {"id": self.video, "creator_id": self.creator, "title": "Live", "description": "",
                "state": "published", "created_at": "2026-11-11T12:00:00Z", **metadata(owned=True),
                "category": "hipco", **changes}

    def edit(self, answer, fields):
        with patch("service.media._owned_creator", return_value=(self.creator, None)), \
                patch("service.media.signed_internal_request", return_value=Response(200, json.dumps(answer).encode())):
            request = self.factory.patch("/api/v1/videos/id", fields, content_type="application/json")
            return media.manage_own_video(request, self.video)

    def test_held_edit_is_accepted_when_the_proposal_carries_it(self):
        held = self.item(edit_review=pending(title="New"))
        self.assertEqual(self.edit(held, {"title": "New"}).status_code, 200)
        # A proposal that does not carry the edit, or a held edit on an unpublished video, is refused.
        self.assertEqual(self.edit(self.item(edit_review=pending(title="Other")), {"title": "New"}).status_code, 503)
        self.assertEqual(self.edit(self.item(state="rejected", edit_review=pending(title="New")), {"title": "New"}).status_code, 503)
        self.assertEqual(self.edit(self.item(), {"title": "New"}).status_code, 503)

    def test_owned_items_require_a_valid_edit_review_and_public_items_never_carry_one(self):
        self.assertTrue(valid_video(self.item(), creator_id=self.creator))
        self.assertFalse(valid_video({key: value for key, value in self.item().items() if key != "edit_review"},
                                     creator_id=self.creator))
        self.assertFalse(valid_video(self.item(visibility="public"), public=True))
        decided = {"id": str(uuid4()), "status": "rejected", "submitted_at": "2026-11-25T12:00:00+00:00",
                   "decided_at": "2026-11-25T13:00:00+00:00", "reason_code": "REVIEWED_EDIT_REJECT", "proposed": None}
        self.assertTrue(valid_edit_review(decided))
        self.assertTrue(valid_edit_review(pending(title="New")))
        for bad in ({"proposed": VALUES}, {"decided_at": None}, {"status": "superseded"}, {"reason_code": "lower"}):
            self.assertFalse(valid_edit_review(decided | bad))
        self.assertFalse(valid_edit_review(pending() | {"decided_at": "2026-11-25T13:00:00+00:00"}))
        self.assertFalse(valid_edit_review(pending(tags=["Bad Tag"])))

    def reviewer(self, operation, request, target=None, forward=JsonResponse({})):
        actor = str(uuid4())
        with patch("service.moderation.authenticated_actor", return_value=(actor, "moderator")), \
                patch("service.standing.identity_context", return_value={"account_id": actor, "mfa_verified": True}), \
                patch("service.moderation._forward", return_value=forward) as call:
            response = moderation_endpoint(request, operation, target_id=target)
        return response, call, actor

    def test_reviewer_routes_forward_bound_data_with_mfa(self):
        target = str(uuid4())
        response, call, actor = self.reviewer("edit_queue", self.factory.get("/edits"))
        call.assert_called_once_with("edit_queue", actor, "moderator", {"cursor": None}, mfa_verified=True)
        response, call, _ = self.reviewer("edit_queue", self.factory.get("/edits", {"status": "pending"}))
        self.assertEqual(response.status_code, 400)
        call.assert_not_called()
        response, call, actor = self.reviewer("edit_detail", self.factory.get("/edits/x"), target)
        call.assert_called_once_with("edit_detail", actor, "moderator", {"target_id": target}, mfa_verified=True)
        request = self.factory.post("/edits/x/decisions", {"action": "approve", "reason": "Matches the video"},
                                    content_type="application/json", HTTP_IDEMPOTENCY_KEY="edit-decision-key-0001")
        response, call, actor = self.reviewer("edit_decision", request, target)
        call.assert_called_once_with("edit_decision", actor, "moderator", {
            "action": "approve", "reason": "Matches the video", "target_id": target, "key": "edit-decision-key-0001"},
            mfa_verified=True)
        with patch("service.moderation.authenticated_actor", return_value=(str(uuid4()), "creator")), \
                patch("service.moderation._forward") as call:
            self.assertEqual(moderation_endpoint(self.factory.get("/edits"), "edit_queue").status_code, 403)
            call.assert_not_called()

    def test_reviewer_answers_are_checked(self):
        item = {"id": str(uuid4()), "video_id": self.video, "title": "New", "submitted_at": "2026-11-25T12:00:00+00:00"}
        self.assertTrue(_valid_result("edit_queue", {"items": [item], "next_cursor": None}))
        self.assertFalse(_valid_result("edit_queue", {"items": [item | {"creator_id": self.creator}], "next_cursor": None}))
        detail = {"edit": {"id": str(uuid4()), "video_id": self.video, "status": "pending",
                           "submitted_at": "2026-11-25T12:00:00+00:00", "video_state": "published",
                           "live": VALUES, "proposed": VALUES | {"title": "New"}},
                  "decisions": [{"id": str(uuid4()), "action": "approve", "status": "applied", "reason": "Fine text",
                                 "created_at": "2026-11-25T12:30:00+00:00"}]}
        self.assertTrue(valid_edit_detail(detail))
        self.assertFalse(valid_edit_detail(detail | {"edit": detail["edit"] | {"creator_id": self.creator}}))
        self.assertFalse(valid_edit_detail(detail | {"edit": detail["edit"] | {"proposed": {"title": "x"}}}))
        decision = {"id": str(uuid4()), "video_id": self.video, "action": "approve", "status": "applied"}
        self.assertTrue(_valid_result("edit_decision", decision))
