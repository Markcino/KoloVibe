"""Administrator creator onboarding: find by email, invite, review applications."""

import uuid
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from tests import test_admin


class CreatorConsoleTests(TestCase):
    setUp = test_admin.AdminConsoleTests.setUp
    login = test_admin.AdminConsoleTests.login

    def person(self, **changes):
        self.candidate_id = str(uuid.uuid4())
        return (200, {"account_id": self.candidate_id, "display_name": "Ada Eze", "role": "viewer",
                      "email_verified": True, **changes})

    def pending(self, *handles):
        rows = sorted(({"account_id": str(uuid.uuid4()), "status": "pending", "creator_id": str(uuid.uuid4()), "handle": h,
                        "submitted_at": timezone.now().isoformat()} for h in handles), key=lambda r: r["account_id"])
        return rows, (200, {"items": rows, "next_cursor": None})

    def open(self, *replies, method="get", data=None):
        with patch("web.views._api", side_effect=[(200, self.account), *replies]) as api:
            client = self.client.post if method == "post" else self.client.get
            return client("/admin/creators/", data or {}), api

    def test_page_lists_waiting_applications_and_offers_the_invite_form(self):
        self.login("administrator")
        rows, page = self.pending("ada_eze", "bola_a")
        response, api = self.open(page)
        self.assertContains(response, "Invite someone")
        self.assertContains(response, "@ada_eze")
        self.assertContains(response, "2 waiting")
        self.assertContains(response, "Approve")
        self.assertEqual(api.call_args.args[0], "/creator-applications")
        empty, _ = self.open(self.pending()[1])
        self.assertContains(empty, "No applications are waiting.")

    def test_only_administrators_see_the_page_and_nothing_is_requested_for_others(self):
        self.login("moderator")
        response, api = self.open()
        self.assertContains(response, "Access denied", status_code=403)
        self.assertEqual(api.call_count, 1)
        post, api = self.open(method="post", data={"operation": "lookup", "email": "a@example.test"})
        self.assertEqual(post.status_code, 403)
        self.assertEqual(api.call_count, 1)

    def test_lookup_shows_who_was_found_before_anything_is_sent(self):
        self.login("administrator")
        found = self.person()
        response, api = self.open(found, self.pending()[1], method="post", data={"operation": "lookup", "email": " Ada@Example.test "})
        self.assertContains(response, "Ada Eze")
        self.assertContains(response, "Email verified")
        self.assertContains(response, "Send creator invitation")
        lookup = api.call_args_list[1]
        self.assertEqual((lookup.args[0], lookup.kwargs["method"], lookup.kwargs["data"]),
                         ("/admin/accounts/lookup", "POST", {"email": "Ada@Example.test"}))
        self.assertNotIn("/creator-invitations", [call.args[0] for call in api.call_args_list])
        unverified = self.open(self.person(email_verified=False), self.pending()[1], method="post",
                               data={"operation": "lookup", "email": "ada@example.test"})[0]
        self.assertContains(unverified, "cannot apply until they verify")

    def test_lookup_failures_are_explained_without_revealing_more(self):
        self.login("administrator")
        for code, text, status in ((404, "must register in the app first", 404), (429, "Too many lookups", 429),
                                   (403, "Only administrators", 403), (503, "unavailable right now", 503)):
            response, _ = self.open((code, {"detail": "x"}), self.pending()[1], method="post",
                                    data={"operation": "lookup", "email": "ada@example.test"})
            self.assertContains(response, text, status_code=status)
        response, api = self.open(self.pending()[1], method="post", data={"operation": "lookup", "email": "nope"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(api.call_count, 2, "an invalid email must not reach Identity")

    def invite_intent(self):
        found = self.person()
        response, _ = self.open(found, self.pending()[1], method="post", data={"operation": "lookup", "email": "ada@example.test"})
        return response.context["candidate"]["intent"]

    def test_invitation_uses_the_confirmed_account_only_and_reports_the_outcome_once(self):
        self.login("administrator")
        intent = self.invite_intent()
        account = self.candidate_id
        for code, text in ((201, "Invitation recorded"), (200, "already invited")):
            summary = {"account_id": account, "status": "invited", "creator_id": None}
            response, api = self.open((code, summary), method="post",
                                      data={"operation": "invite", "account_id": account, "intent": intent})
            self.assertRedirects(response, "/admin/creators/", fetch_redirect_response=False)
            call = api.call_args_list[1]
            self.assertEqual((call.args[0], call.kwargs["method"], call.kwargs["data"]),
                             ("/creator-invitations", "POST", {"account_id": account}))
            page, _ = self.open(self.pending()[1])
            self.assertContains(page, text)
            self.assertNotContains(self.open(self.pending()[1])[0], text)

    def test_invitation_rejects_forged_other_account_and_failing_replies(self):
        self.login("administrator")
        intent = self.invite_intent()
        account = self.candidate_id
        for data in ({"operation": "invite", "account_id": account, "intent": "forged"},
                     {"operation": "invite", "account_id": str(uuid.uuid4()), "intent": intent},
                     {"operation": "invite", "account_id": "x", "intent": intent}):
            response, api = self.open(method="post", data=data)
            self.assertEqual(response.status_code, 400, data)
            self.assertEqual(api.call_count, 1)
        for reply, status in (((403, {"detail": "Self-review is forbidden"}), 403), ((503, {}), 503),
                              ((201, {"account_id": str(uuid.uuid4()), "status": "invited", "creator_id": None}), 503)):
            response, _ = self.open(reply, self.pending()[1], method="post",
                                    data={"operation": "invite", "account_id": account, "intent": intent})
            self.assertEqual(response.status_code, status, reply)
            self.assertNotIn("creator_notice", self.client.session)

    def decision_data(self, row, decision, intent, **extra):
        return {"operation": "decide", "account_id": row["account_id"], "handle": row["handle"], "decision": decision,
                "intent": intent, **extra}

    def test_decisions_are_confirmed_first_then_sent_with_the_decision_only(self):
        self.login("administrator")
        rows, page = self.pending("ada_eze")
        listing, _ = self.open(page)
        row = listing.context["applications"][0]
        for decision, word in (("approved", "approval"), ("rejected", "rejection")):
            asked, api = self.open(method="post", data=self.decision_data(row, decision, row["intent"]))
            self.assertContains(asked, f"Confirm {word}")
            self.assertContains(asked, "@ada_eze")
            self.assertEqual(api.call_count, 1, "confirmation must not reach the gateway")
            summary = {"account_id": row["account_id"], "status": decision, "creator_id": row["creator_id"]}
            done, api = self.open((200, summary), method="post", data=self.decision_data(row, decision, row["intent"], confirmed="1"))
            self.assertRedirects(done, "/admin/creators/", fetch_redirect_response=False)
            call = api.call_args_list[1]
            self.assertEqual((call.args[0], call.kwargs["data"]),
                             (f"/creator-applications/{row['account_id']}/decision", {"decision": decision}))
        self.assertContains(self.open(page)[0], "Application rejected.")

    def test_decisions_reject_tampering_and_surface_service_refusals(self):
        self.login("administrator")
        rows, page = self.pending("ada_eze")
        row = self.open(page)[0].context["applications"][0]
        bad = (self.decision_data(row, "approved", "forged", confirmed="1"), self.decision_data(row, "maybe", row["intent"], confirmed="1"),
               self.decision_data({**row, "account_id": str(uuid.uuid4())}, "approved", row["intent"], confirmed="1"))
        for data in bad:
            response, api = self.open(method="post", data=data)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(api.call_count, 1)
        for code, text in ((403, "own application"), (404, "no longer exists"), (409, "already been decided")):
            response, _ = self.open((code, {"detail": "x"}), page, method="post",
                                    data=self.decision_data(row, "approved", row["intent"], confirmed="1"))
            self.assertContains(response, text, status_code=code)
        mismatch = {"account_id": row["account_id"], "status": "rejected", "creator_id": None}
        response, _ = self.open((200, mismatch), page, method="post", data=self.decision_data(row, "approved", row["intent"], confirmed="1"))
        self.assertEqual(response.status_code, 503)

    def test_page_degrades_when_applications_cannot_be_read(self):
        self.login("administrator")
        for reply in ((503, {}), (200, {"items": [], "next_cursor": None, "extra": 1}),
                      (200, {"items": [{"account_id": str(uuid.uuid4()), "status": "pending", "creator_id": str(uuid.uuid4()),
                                        "handle": "BAD HANDLE", "submitted_at": "2026-11-23T10:00:00Z"}], "next_cursor": None})):
            response, _ = self.open(reply)
            self.assertContains(response, "Applications are unavailable")
            self.assertContains(response, "Invite someone")
