"""Decision A (RV2-01): the console's review of held edits to published videos."""

import uuid
from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.urls import reverse

from web.edit_views import valid_edit_page
from .test_admin import AdminConsoleTests

VALUES = {"title": "Live title", "description": "Live text", "category": "hipco", "tags": ["monrovia"]}
REASON = "Reviewed against the content policy."


class EditReviewConsoleTests(TestCase):
    login = AdminConsoleTests.login

    def edit(self, status="pending"):
        return {"edit": {"id": self.target, "video_id": self.video, "status": status,
                         "submitted_at": "2026-11-25T12:00:00Z", "video_state": "published",
                         "live": VALUES, "proposed": VALUES | {"title": "<b>Proposed title</b>"}},
                "decisions": []}

    def setUp(self):
        AdminConsoleTests.setUp(self)
        self.video = str(uuid.uuid4())

    def open_detail(self, status="pending"):
        with patch("web.views._api", side_effect=[(200, self.account), (200, self.edit(status))]) as api:
            response = self.client.get(reverse("moderation-edits-detail", args=[self.target]))
        self.assertEqual(api.call_args_list[1].args, (f"/moderation/edits/{self.target}",))
        return response

    def test_queue_lists_pending_edits_and_rejects_bad_answers(self):
        self.login(role="moderator")
        item = {"id": str(uuid.uuid4()), "video_id": self.video, "title": "<i>New</i>", "submitted_at": "2026-11-25T12:00:00Z"}
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [item], "next_cursor": None})]) as api:
            response = self.client.get(reverse("moderation-edits"))
        self.assertContains(response, "&lt;i&gt;New&lt;/i&gt;")
        self.assertEqual(api.call_args_list[1].args, ("/moderation/edits",))
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [item | {"creator_id": self.video}], "next_cursor": None})]):
            self.assertEqual(self.client.get(reverse("moderation-edits")).status_code, 503)
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.get(reverse("moderation-edits"), {"status": "approved"}).status_code, 400)
        self.assertFalse(valid_edit_page({"items": [item], "next_cursor": "x"}))

    def test_detail_shows_live_and_proposed_text_escaped(self):
        self.login()
        response = self.open_detail()
        self.assertContains(response, "Live title")
        self.assertContains(response, "&lt;b&gt;Proposed title&lt;/b&gt;")
        self.assertContains(response, "Record a decision")
        self.assertNotContains(self.open_detail("approved"), "Record a decision")

    def test_decision_posts_once_per_key_and_binds_the_intent(self):
        self.login()
        intent = self.open_detail().context["intent"]
        result = {"id": str(uuid.uuid4()), "video_id": self.video, "action": "approve", "status": "applied"}
        keys = []
        for _ in range(2):
            with patch("web.views._api", side_effect=[(200, self.account), (200, result)]) as api:
                response = self.client.post(reverse("moderation-edits-detail", args=[self.target]),
                                            {"intent": intent, "action": "approve", "reason": REASON})
            self.assertContains(response, "The proposed text is now live.")
            call = api.call_args_list[1]
            self.assertEqual(call.args, (f"/moderation/edits/{self.target}/decisions",))
            self.assertEqual((call.kwargs["method"], call.kwargs["data"]), ("POST", {"action": "approve", "reason": REASON}))
            keys.append(call.kwargs["idempotency_key"])
        self.assertEqual(keys[0], keys[1])
        other = reverse("moderation-edits-detail", args=[str(uuid.uuid4())])
        payload = signing.loads(intent, salt="admin-edit-decision")
        for url, data in ((other, {"intent": intent, "action": "approve", "reason": REASON}),
                          (reverse("moderation-edits-detail", args=[self.target]), {"intent": intent, "action": "publish", "reason": REASON}),
                          (reverse("moderation-edits-detail", args=[self.target]), {"intent": intent, "action": "reject", "reason": "short"}),
                          (reverse("moderation-edits-detail", args=[self.target]),
                           {"intent": signing.dumps(payload | {"actor": str(uuid.uuid4())}, salt="admin-edit-decision"),
                            "action": "approve", "reason": REASON})):
            with patch("web.views._api", side_effect=[(200, self.account)]) as api:
                self.assertEqual(self.client.post(url, data).status_code, 400)
            self.assertEqual(len(api.call_args_list), 1)

    def test_a_mismatched_decision_answer_is_not_shown_as_success(self):
        self.login()
        intent = self.open_detail().context["intent"]
        wrong = {"id": str(uuid.uuid4()), "video_id": str(uuid.uuid4()), "action": "approve", "status": "applied"}
        with patch("web.views._api", side_effect=[(200, self.account), (200, wrong)]):
            response = self.client.post(reverse("moderation-edits-detail", args=[self.target]),
                                        {"intent": intent, "action": "approve", "reason": REASON})
        self.assertEqual(response.status_code, 503)
