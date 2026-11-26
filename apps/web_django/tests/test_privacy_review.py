"""Decision C: the console's privacy request review and account holds pages."""

import uuid
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .test_admin import AdminConsoleTests


class PrivacyReviewConsoleTests(TestCase):
    login = AdminConsoleTests.login

    def setUp(self):
        AdminConsoleTests.setUp(self)
        self.request_id, self.person = str(uuid.uuid4()), str(uuid.uuid4())

    def row(self, **extra):
        return {"id": self.request_id, "account_id": self.person, "kind": "deletion", "status": "received",
                "created_at": "2026-11-26T10:00:00+00:00", "review_started_at": None, "decided_at": None,
                "decline_code": None, "held": False} | extra

    def hold(self, **extra):
        return {"id": str(uuid.uuid4()), "account_id": self.person, "reason_code": "LEGAL_CLAIM",
                "note": "<i>Open dispute</i>", "placed_by": self.account["id"],
                "placed_at": "2026-11-26T11:00:00+00:00", "released_at": None} | extra

    def open(self, items, query=""):
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": items, "next_cursor": None})]) as api:
            response = self.client.get(reverse("privacy-requests") + query)
        return response, api

    def test_only_administrators_and_known_filters(self):
        self.login(role="moderator")
        with patch("web.views._api", side_effect=[(200, self.account)]) as api:
            self.assertEqual(self.client.get(reverse("privacy-requests")).status_code, 403)
        self.assertEqual(api.call_count, 1)
        self.login()
        for query in ("?status=erased", "?cursor=nope", "?other=1"):
            with patch("web.views._api", side_effect=[(200, self.account)]):
                self.assertEqual(self.client.get(reverse("privacy-requests") + query).status_code, 400)
        response, api = self.open([], "?status=in_review")
        self.assertEqual(api.call_args_list[1].args, ("/admin/privacy-requests?status=in_review",))
        self.assertContains(response, "No privacy requests with this status")

    def test_actions_follow_the_state_and_bad_answers_are_refused(self):
        self.login()
        response, _ = self.open([self.row()])
        self.assertContains(response, "Open review")
        self.assertNotContains(response, "Approve deletion")
        self.assertContains(response, "never marked completed by hand")
        response, _ = self.open([self.row(status="in_review")])
        self.assertContains(response, "Approve deletion")
        self.assertContains(response, "Decline")
        response, _ = self.open([self.row(status="in_review", held=True)])
        self.assertNotContains(response, "Approve deletion")
        self.assertContains(response, "Release the hold to approve")
        response, _ = self.open([self.row(status="in_review", kind="access")])
        self.assertNotContains(response, "Approve deletion")
        response, _ = self.open([self.row(status="declined")])
        self.assertContains(response, "unavailable", msg_prefix="declined without a code is refused")

    def test_approve_needs_the_bound_intent_and_the_confirmation(self):
        self.login()
        response, _ = self.open([self.row(status="in_review")])
        intent = response.context["rows"][0]["actions"]["approve"]
        form = {"operation": "approve-deletion", "request_id": self.request_id, "intent": intent}
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [], "next_cursor": None})]) as api:
            self.assertEqual(self.client.post(reverse("privacy-requests"), form).status_code, 400)
        self.assertEqual(api.call_count, 2, "no change was sent without the confirmation")
        done = self.row(status="processing", decided_at="2026-11-26T12:00:00+00:00")
        with patch("web.views._api", side_effect=[(200, self.account), (200, done)]) as api:
            response = self.client.post(reverse("privacy-requests"), form | {"confirm": "yes"})
        self.assertRedirects(response, reverse("privacy-requests"), fetch_redirect_response=False)
        self.assertEqual(api.call_args_list[1].args, (f"/admin/privacy-requests/{self.request_id}/approve-deletion",))
        self.assertNotIn("data", api.call_args_list[1].kwargs)
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.post(reverse("privacy-requests"),
                                              form | {"confirm": "yes", "request_id": str(uuid.uuid4())}).status_code, 400)
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.post(reverse("privacy-requests"),
                                              form | {"confirm": "yes", "operation": "decline"}).status_code, 400)

    def test_conflicts_use_fixed_copy_and_never_echo_identity(self):
        self.login()
        response, _ = self.open([self.row(status="in_review")])
        form = {"operation": "approve-deletion", "request_id": self.request_id, "confirm": "yes",
                "intent": response.context["rows"][0]["actions"]["approve"]}
        with patch("web.views._api", side_effect=[(200, self.account),
                                                   (409, {"detail": "secret text", "code": "account_on_hold"}),
                                                   (200, {"items": [], "next_cursor": None})]):
            response = self.client.post(reverse("privacy-requests"), form)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Release the hold before approving", status_code=409)
        self.assertNotContains(response, "secret text", status_code=409)

    def test_decline_sends_only_a_known_code(self):
        self.login()
        response, _ = self.open([self.row(status="in_review")])
        form = {"operation": "decline", "request_id": self.request_id,
                "intent": response.context["rows"][0]["actions"]["decline"]}
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [], "next_cursor": None})]):
            self.assertEqual(self.client.post(reverse("privacy-requests"), form | {"decline_code": "BECAUSE"}).status_code, 400)
        declined = self.row(status="declined", decline_code="WITHDRAWN", decided_at="2026-11-26T12:00:00+00:00")
        with patch("web.views._api", side_effect=[(200, self.account), (200, declined)]) as api:
            self.assertEqual(self.client.post(reverse("privacy-requests"), form | {"decline_code": "WITHDRAWN"}).status_code, 302)
        self.assertEqual(api.call_args_list[1].kwargs["data"], {"decline_code": "WITHDRAWN"})

    def test_holds_are_escaped_placed_and_released(self):
        self.login()
        hold = self.hold()
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [hold]})]) as api:
            response = self.client.get(reverse("account-holds", args=[self.person]))
        self.assertEqual(api.call_args_list[1].args, (f"/admin/accounts/{self.person}/holds",))
        self.assertContains(response, "&lt;i&gt;Open dispute&lt;/i&gt;")
        place = {"operation": "place", "intent": response.context["place_intent"], "reason_code": "LEGAL_CLAIM",
                 "note": "Dispute about uploads"}
        with patch("web.views._api", side_effect=[(200, self.account), (201, self.hold())]) as api:
            self.assertEqual(self.client.post(reverse("account-holds", args=[self.person]), place).status_code, 302)
        self.assertEqual(api.call_args_list[1].kwargs["data"], {"reason_code": "LEGAL_CLAIM", "note": "Dispute about uploads"})
        release = {"operation": "release", "hold_id": hold["id"], "intent": response.context["rows"][0]["intent"]}
        with patch("web.views._api", side_effect=[(200, self.account), (200, hold | {"released_at": "2026-11-26T12:00:00+00:00"})]) as api:
            self.assertEqual(self.client.post(reverse("account-holds", args=[self.person]), release).status_code, 302)
        self.assertEqual(api.call_args_list[1].args, (f"/admin/account-holds/{hold['id']}/release",))
        other = str(uuid.uuid4())
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.post(reverse("account-holds", args=[other]), place).status_code, 400,
                             "an intent for one account is refused for another")
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [self.hold(account_id=other)]})]):
            self.assertContains(self.client.get(reverse("account-holds", args=[self.person])), "unavailable")
