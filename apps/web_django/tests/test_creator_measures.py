"""Decision F (D-8): the console's creator measures and appeal decisions."""

import uuid
from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.urls import reverse

from web.restriction_views import valid_appeal_page, valid_measure
from .test_admin import AdminConsoleTests

REASON = "Repeated spam uploads after a warning"


class CreatorMeasureConsoleTests(TestCase):
    login = AdminConsoleTests.login

    def setUp(self):
        AdminConsoleTests.setUp(self)
        self.creator, self.measure_id = str(uuid.uuid4()), str(uuid.uuid4())

    def measure(self, **extra):
        return {"id": self.measure_id, "kind": "upload", "reason_code": "SPAM_REPEAT",
                "policy_version": "creator-enforcement-v1", "issued_at": "2026-11-25T12:00:00+00:00",
                "expires_at": None, "lifted_at": None, "active": True, "appeal": None, "creator_id": self.creator,
                "reason": "<b>" + REASON + "</b>", "issued_by": str(uuid.uuid4()), "lifted_by": None,
                "lift_reason": ""} | extra

    def appeal(self, **extra):
        return {"id": str(uuid.uuid4()), "status": "open", "created_at": "2026-11-25T12:30:00+00:00",
                "reason": "These were my own original videos", "restriction": self.measure(),
                "decided_at": None, "decision_reason": ""} | extra

    def page(self, items=None):
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": items or [self.measure()]})]) as api:
            response = self.client.get(reverse("creator-measures", args=[self.creator]))
        self.assertEqual(api.call_args_list[1].args, (f"/admin/creators/{self.creator}/restrictions",))
        return response

    def issue(self, intent, **fields):
        data = {"operation": "issue", "intent": intent, "kind": "upload", "reason_code": "SPAM_REPEAT",
                "policy_version": "creator-enforcement-v1", "reason": REASON, "expires_at": ""} | fields
        return data

    def test_moderators_cannot_open_any_measure_page(self):
        self.login(role="moderator")
        for url in (reverse("creator-measures-find"), reverse("creator-measure-appeals"),
                    reverse("creator-measures", args=[self.creator])):
            with patch("web.views._api", side_effect=[(200, self.account)]) as api:
                self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(api.call_count, 1)

    def test_find_searches_by_handle_or_opens_by_id(self):
        self.login()
        item = {"id": self.creator, "handle": "restricted_creator", "bio": "", "status": "active",
                "display_name": "<i>Name</i>", "location": ""}
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [item], "next_cursor": None})]) as api:
            response = self.client.get(reverse("creator-measures-find"), {"q": "restricted"})
        self.assertContains(response, "@restricted_creator")
        self.assertContains(response, "&lt;i&gt;Name&lt;/i&gt;")
        self.assertEqual(api.call_args_list[1].args, ("/creators/search?q=restricted",))
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [item | {"user_id": self.creator}], "next_cursor": None})]):
            self.assertContains(self.client.get(reverse("creator-measures-find"), {"q": "restricted"}), "unavailable")
        with patch("web.views._api", side_effect=[(200, self.account)]):
            response = self.client.get(reverse("creator-measures-find"), {"creator": self.creator})
        self.assertRedirects(response, reverse("creator-measures", args=[self.creator]), fetch_redirect_response=False)
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.get(reverse("creator-measures-find"), {"creator": "nope"}).status_code, 400)

    def test_creator_page_lists_measures_escaped_and_rejects_bad_answers(self):
        self.login()
        response = self.page()
        self.assertContains(response, "&lt;b&gt;" + REASON)
        self.assertContains(response, "Lift measure")
        self.assertContains(response, "Issue measure")
        other = self.measure(creator_id=str(uuid.uuid4()))
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [other]})]):
            response = self.client.get(reverse("creator-measures", args=[self.creator]))
        self.assertContains(response, "unavailable")
        self.assertNotContains(response, "Issue measure")

    def test_issue_posts_once_per_key_and_shows_refusals_without_echoing(self):
        self.login()
        intent = self.page().context["issue_intent"]
        keys = []
        for status in (201, 200):
            with patch("web.views._api", side_effect=[(200, self.account), (status, self.measure())]) as api:
                response = self.client.post(reverse("creator-measures", args=[self.creator]), self.issue(intent))
            self.assertRedirects(response, reverse("creator-measures", args=[self.creator]), fetch_redirect_response=False)
            call = api.call_args_list[1]
            self.assertEqual(call.args, (f"/admin/creators/{self.creator}/restrictions",))
            self.assertEqual(call.kwargs["data"], {"kind": "upload", "reason_code": "SPAM_REPEAT",
                                                   "policy_version": "creator-enforcement-v1", "reason": REASON,
                                                   "expires_at": None})
            keys.append(call.kwargs["idempotency_key"])
        self.assertEqual(keys[0], keys[1])
        with patch("web.views._api", side_effect=[(200, self.account), (403, {"detail": "secret detail"}),
                                                  (200, {"items": []})]):
            response = self.client.post(reverse("creator-measures", args=[self.creator]), self.issue(intent))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "restrict your own creator profile", status_code=403)
        self.assertContains(response, "Issue measure", status_code=403)
        self.assertNotContains(response, "secret detail", status_code=403)

    def test_issue_input_and_intent_are_checked_before_sending(self):
        self.login()
        intent = self.page().context["issue_intent"]
        payload = signing.loads(intent, salt="admin-creator-measures")
        other = reverse("creator-measures", args=[str(uuid.uuid4())])
        for url, data in ((other, self.issue(intent)),
                          (reverse("creator-measures", args=[self.creator]),
                           self.issue(signing.dumps(payload | {"actor": str(uuid.uuid4())}, salt="admin-creator-measures")))):
            with patch("web.views._api", side_effect=[(200, self.account)]) as api:
                self.assertEqual(self.client.post(url, data).status_code, 400)
            self.assertEqual(api.call_count, 1)
        for bad in ({"kind": "ban"}, {"reason_code": "lower"}, {"reason": "short"}, {"expires_at": "2020-01-01T00:00"}):
            with self.subTest(bad), patch("web.views._api", side_effect=[(200, self.account), (200, {"items": []})]) as api:
                self.assertEqual(self.client.post(reverse("creator-measures", args=[self.creator]), self.issue(intent, **bad)).status_code, 400)
            self.assertEqual([call.kwargs.get("method", "GET") for call in api.call_args_list[1:]], ["GET"])

    def test_future_end_time_is_sent_as_utc(self):
        self.login()
        intent = self.page().context["issue_intent"]
        with patch("web.views._api", side_effect=[(200, self.account), (201, self.measure(expires_at="2099-01-01T10:30:00+00:00"))]) as api:
            self.client.post(reverse("creator-measures", args=[self.creator]), self.issue(intent, expires_at="2099-01-01T10:30"))
        self.assertEqual(api.call_args_list[1].kwargs["data"]["expires_at"], "2099-01-01T10:30:00+00:00")

    def test_lift_is_bound_to_the_measure_and_creator(self):
        self.login()
        lift = self.page().context["items"][0]["lift_intent"]
        lifted = self.measure(active=False, lifted_at="2026-11-25T13:00:00+00:00", lifted_by=str(uuid.uuid4()),
                              lift_reason="Reviewed and reinstated")
        with patch("web.views._api", side_effect=[(200, self.account), (200, lifted)]) as api:
            response = self.client.post(reverse("creator-measures", args=[self.creator]), {
                "operation": "lift", "restriction_id": self.measure_id, "intent": lift, "lift_reason": "Reviewed and reinstated"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(api.call_args_list[1].args, (f"/admin/creator-restrictions/{self.measure_id}/lift",))
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.post(reverse("creator-measures", args=[self.creator]), {
                "operation": "lift", "restriction_id": str(uuid.uuid4()), "intent": lift,
                "lift_reason": "Reviewed and reinstated"}).status_code, 400)

    def test_appeal_queue_decides_with_a_bound_intent(self):
        self.login()
        appeal = self.appeal()
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [appeal], "next_cursor": None})]) as api:
            response = self.client.get(reverse("creator-measure-appeals"))
        self.assertContains(response, "These were my own original videos")
        self.assertEqual(api.call_args_list[1].args, ("/admin/creator-restriction-appeals",))
        intent = response.context["items"][0]["intent"]
        decided = appeal | {"status": "lifted", "decided_at": "2026-11-25T13:00:00+00:00", "decision_reason": "Evidence shows original work"}
        with patch("web.views._api", side_effect=[(200, self.account), (200, decided)]) as api:
            response = self.client.post(reverse("creator-measure-appeals"), {
                "appeal_id": appeal["id"], "intent": intent, "decision": "lift", "reason": "Evidence shows original work"})
        self.assertRedirects(response, reverse("creator-measure-appeals"), fetch_redirect_response=False)
        self.assertEqual(api.call_args_list[1].kwargs["data"], {"decision": "lift", "reason": "Evidence shows original work"})
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.post(reverse("creator-measure-appeals"), {
                "appeal_id": str(uuid.uuid4()), "intent": intent, "decision": "lift",
                "reason": "Evidence shows original work"}).status_code, 400)

    def test_validators(self):
        self.assertTrue(valid_measure(self.measure()))
        self.assertFalse(valid_measure(self.measure(active=True, lifted_at="2026-11-25T13:00:00+00:00")))
        self.assertFalse(valid_measure(self.measure(kind="ban")))
        self.assertFalse(valid_measure({k: v for k, v in self.measure().items() if k != "reason"}))
        appeal = self.appeal()
        self.assertTrue(valid_appeal_page({"items": [appeal], "next_cursor": appeal["id"]}))
        self.assertFalse(valid_appeal_page({"items": [appeal], "next_cursor": str(uuid.uuid4())}))
        self.assertFalse(valid_appeal_page({"items": [appeal | {"status": "lifted"}], "next_cursor": None}))
