"""Decision E (D11-008): the console's rights-holder verification page."""

import uuid
from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.urls import reverse

from .test_admin import AdminConsoleTests

EVIDENCE = "Signed letter from the label confirming authority"


class RightsHolderConsoleTests(TestCase):
    login = AdminConsoleTests.login

    def setUp(self):
        AdminConsoleTests.setUp(self)
        self.holder = str(uuid.uuid4())

    def row(self, **extra):
        return {"account_id": self.holder, "organisation": "<b>Monrovia Records</b>", "evidence": EVIDENCE,
                "verified_by": self.account["id"], "verified_at": "2026-11-25T12:00:00+00:00", "revoked_at": None,
                "active": True} | extra

    def open(self, items=None):
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": items or [], "next_cursor": None})]) as api:
            response = self.client.get(reverse("rights-holders"))
        self.assertEqual(api.call_args_list[1].args, ("/admin/rights-holders",))
        return response

    def test_moderators_are_refused_before_any_call(self):
        self.login(role="moderator")
        with patch("web.views._api", side_effect=[(200, self.account)]) as api:
            self.assertEqual(self.client.get(reverse("rights-holders")).status_code, 403)
        self.assertEqual(api.call_count, 1)

    def test_list_is_escaped_and_bad_answers_are_refused(self):
        self.login()
        response = self.open([self.row()])
        self.assertContains(response, "&lt;b&gt;Monrovia Records&lt;/b&gt;")
        self.assertContains(response, "Revoke")
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [self.row(active=False)], "next_cursor": None})]):
            self.assertContains(self.client.get(reverse("rights-holders")), "unavailable")

    def test_lookup_then_verify_with_a_bound_intent(self):
        self.login()
        candidate = {"account_id": self.holder, "display_name": "Label manager", "role": "viewer", "email_verified": True}
        with patch("web.views._api", side_effect=[(200, self.account), (200, candidate), (200, {"items": [], "next_cursor": None})]):
            response = self.client.post(reverse("rights-holders"), {"operation": "lookup", "email": "label@example.test"})
        intent = response.context["candidate"]["intent"]
        form = {"operation": "verify", "account_id": self.holder, "intent": intent,
                "organisation": "Monrovia Records", "evidence": EVIDENCE}
        with patch("web.views._api", side_effect=[(200, self.account), (201, self.row())]) as api:
            response = self.client.post(reverse("rights-holders"), form)
        self.assertRedirects(response, reverse("rights-holders"), fetch_redirect_response=False)
        self.assertEqual(api.call_args_list[1].kwargs["data"],
                         {"account_id": self.holder, "organisation": "Monrovia Records", "evidence": EVIDENCE})
        other = str(uuid.uuid4())
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.post(reverse("rights-holders"), form | {"account_id": other}).status_code, 400)
        forged = signing.dumps(signing.loads(intent, salt="admin-rights-holders") | {"actor": other}, salt="admin-rights-holders")
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.post(reverse("rights-holders"), form | {"intent": forged}).status_code, 400)
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [], "next_cursor": None})]) as api:
            self.assertEqual(self.client.post(reverse("rights-holders"), form | {"evidence": "short"}).status_code, 400)
        self.assertEqual(len(api.call_args_list), 2)

    def test_revoke_sends_no_body_and_refusals_use_fixed_copy(self):
        self.login()
        intent = self.open([self.row()]).context["rows"][0]["intent"]
        form = {"operation": "revoke", "account_id": self.holder, "intent": intent}
        revoked = self.row(active=False, revoked_at="2026-11-25T13:00:00+00:00")
        with patch("web.views._api", side_effect=[(200, self.account), (200, revoked)]) as api:
            self.assertEqual(self.client.post(reverse("rights-holders"), form).status_code, 302)
        call = api.call_args_list[1]
        self.assertEqual(call.args, (f"/admin/rights-holders/{self.holder}/revoke",))
        self.assertNotIn("data", call.kwargs)
        with patch("web.views._api", side_effect=[(200, self.account), (403, {"detail": "secret"}),
                                                  (200, {"items": [], "next_cursor": None})]):
            response = self.client.post(reverse("rights-holders"), form)
        self.assertContains(response, "your own account", status_code=403)
        self.assertNotContains(response, "secret", status_code=403)
