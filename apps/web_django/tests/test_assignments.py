"""Administrator-only moderator assignment controls on review items."""

import uuid
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from tests import test_admin


class AssignmentWebTests(TestCase):
    setUp = test_admin.AdminConsoleTests.setUp
    login = test_admin.AdminConsoleTests.login
    record = test_admin.AdminConsoleTests.record
    detail = test_admin.AdminConsoleTests.detail

    def moderators(self, *names, status="accepted"):
        self.people = {str(uuid.uuid4()): name for name in names}
        rows = [{"id": str(uuid.uuid4()), "display_name": name, "email_masked": "m***@example.test",
                 "status": status, "expires_at": "2026-11-25T10:00:00+00:00",
                 **({"account_id": account} if status == "accepted" else {})} for account, name in self.people.items()]
        return (200, {"items": rows, "next_cursor": None})

    def listing(self, *assigned):
        return (200, {"scope": "reports", "target_id": self.target,
                      "items": [{"moderator_id": value} for value in sorted(assigned)]})

    def open_detail(self, *replies):
        with patch("web.views._api", side_effect=[(200, self.account), (200, self.detail("reports")), *replies]) as api:
            response = self.client.get(reverse("moderation-reports-detail", args=[self.target]))
        return response, api

    def test_administrator_sees_assigned_and_assignable_moderators(self):
        self.login("administrator")
        roster = self.moderators("Ada Reviewer", "Bola Reviewer")
        first, second = sorted(self.people)
        response, api = self.open_detail(self.listing(first), roster)
        self.assertEqual(response.status_code, 200)
        panel = response.context["assignments"]
        self.assertTrue(panel["available"])
        self.assertEqual([row["id"] for row in panel["assigned"]], [first])
        self.assertEqual([row["id"] for row in panel["candidates"]], [second])
        self.assertContains(response, "Moderator assignments")
        self.assertContains(response, "Assign moderator")
        self.assertContains(response, "Revoke")
        self.assertNotContains(response, "email")
        self.assertEqual(api.call_args_list[2].args[0],
                         f"/admin/moderation/assignments?scope=reports&target={self.target}")

    def test_moderators_never_see_or_load_assignment_controls(self):
        self.login("moderator")
        response, api = self.open_detail()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["assignments"])
        self.assertNotContains(response, "Moderator assignments")
        self.assertEqual(api.call_count, 2)

    def test_unavailable_or_malformed_assignment_data_degrades_without_hiding_the_review(self):
        self.login("administrator")
        for replies in (((503, {}),), (self.listing(), (503, {})),
                        ((200, {"scope": "reports", "target_id": self.target, "items": [], "extra": 1}), self.moderators("Ada"))):
            response, _ = self.open_detail(*replies)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context["assignments"]["available"])
            self.assertContains(response, "Assignments are unavailable")
            self.assertContains(response, "Submit decision")

    def submit(self, active, replies):
        """Open the page as an administrator, then POST the assignment form with scripted gateway replies."""
        self.login("administrator")
        roster = self.moderators("Ada Reviewer")
        moderator = next(iter(self.people))
        opened, _ = self.open_detail(self.listing(), roster)
        data = {"intent": opened.context["assignments"]["intent"], "moderator_id": moderator, "active": active}
        body = {"scope": "reports", "target_id": self.target, "moderator_id": moderator, "active": active == "1"}
        with patch("web.views._api", side_effect=[(200, self.account), *replies(roster, body)]) as api:
            response = self.client.post(reverse("moderation-reports-assign", args=[self.target]), data)
        return response, api, body

    def test_assignment_grants_and_revokes_through_the_gateway_then_confirms_once(self):
        # The roster was cached when the page opened, so neither granting nor revoking asks Identity again.
        for active, replies in (("1", lambda roster, body: ((200, body),)), ("0", lambda roster, body: ((200, body),))):
            response, api, body = self.submit(active, replies)
            self.assertEqual(response.status_code, 302, active)
            self.assertEqual(response["Location"], reverse("moderation-reports-detail", args=[self.target]))
            write = api.call_args_list[-1]
            self.assertEqual((write.args[0], write.kwargs["method"], write.kwargs["data"]),
                             ("/admin/moderation/assignments", "POST", body))
            self.assertEqual(self.client.session["assignment_notice"], "assigned" if active == "1" else "revoked")
        response, _ = self.open_detail(self.listing(), self.moderators("Ada Reviewer"))
        self.assertContains(response, "Assignment revoked")
        response, _ = self.open_detail(self.listing(), self.moderators("Ada Reviewer"))
        self.assertNotContains(response, "Assignment revoked")

    def test_requests_that_fail_validation_never_write(self):
        self.login("administrator")
        roster = self.moderators("Ada Reviewer")
        known = next(iter(self.people))
        opened, _ = self.open_detail(self.listing(), roster)
        intent = opened.context["assignments"]["intent"]
        url = reverse("moderation-reports-assign", args=[self.target])
        base = {"intent": intent, "moderator_id": known, "active": "1"}
        cases = [({**base, "intent": "forged"}, ()), ({**base, "active": "yes"}, ()), ({**base, "moderator_id": "x"}, ()),
                 ({**base, "moderator_id": str(uuid.uuid4())}, (roster,))]
        for data, replies in cases:
            with patch("web.views._api", side_effect=[(200, self.account), *replies]) as api:
                self.assertEqual(self.client.post(url, data).status_code, 400, data)
            self.assertNotIn("POST", [call.kwargs.get("method") for call in api.call_args_list])
        # An intent signed for another target cannot be replayed here.
        other = reverse("moderation-reports-assign", args=[uuid.uuid4()])
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.post(other, base).status_code, 400)
        # GET is not a mutation.
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.assertEqual(self.client.get(url).status_code, 405)

    def test_moderators_cannot_assign_and_gateway_failures_are_not_reported_as_success(self):
        self.login("moderator")
        url = reverse("moderation-reports-assign", args=[self.target])
        with patch("web.views._api", side_effect=[(200, self.account)]) as api:
            response = self.client.post(url, {"intent": "x", "moderator_id": str(uuid.uuid4()), "active": "1"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(api.call_count, 1)
        self.login("administrator")
        roster = self.moderators("Ada Reviewer")
        known = next(iter(self.people))
        opened, _ = self.open_detail(self.listing(), roster)
        data = {"intent": opened.context["assignments"]["intent"], "moderator_id": known, "active": "1"}
        wrong = {"scope": "reports", "target_id": self.target, "moderator_id": str(uuid.uuid4()), "active": True}
        for reply, expected in (((403, {"detail": "Request unavailable"}), 403), ((404, {}), 404), ((503, {}), 503), ((200, wrong), 503)):
            with patch("web.views._api", side_effect=[(200, self.account), reply]):
                self.assertEqual(self.client.post(url, data).status_code, expected, reply)
            self.assertNotIn("assignment_notice", self.client.session)

    def test_roster_is_cached_briefly_and_refreshed_before_refusing_an_unknown_moderator(self):
        self.login("administrator")
        roster = self.moderators("Ada Reviewer")
        known = next(iter(self.people))
        first, api = self.open_detail(self.listing(), roster)
        self.assertEqual(api.call_count, 4)  # /me, detail, assignments, roster
        second, api = self.open_detail(self.listing())
        self.assertEqual(api.call_count, 3, "second view must reuse the cached roster")
        self.assertEqual([row["id"] for row in second.context["assignments"]["candidates"]], [known])
        # A moderator who joined after the cache was filled is found by one fresh lookup, not refused.
        newcomer = str(uuid.uuid4())
        fresh = (200, {"items": [{"id": str(uuid.uuid4()), "display_name": "New Joiner", "email_masked": "n***@example.test",
                                   "status": "accepted", "expires_at": "2026-11-25T10:00:00+00:00", "account_id": newcomer}], "next_cursor": None})
        body = {"scope": "reports", "target_id": self.target, "moderator_id": newcomer, "active": True}
        data = {"intent": second.context["assignments"]["intent"], "moderator_id": newcomer, "active": "1"}
        with patch("web.views._api", side_effect=[(200, self.account), fresh, (200, body)]) as api:
            response = self.client.post(reverse("moderation-reports-assign", args=[self.target]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(api.call_args_list[1].args[0], "/admin/moderator-invitations")
        # Truly unknown ids are still refused after the fresh lookup, and nothing is written.
        data["moderator_id"] = str(uuid.uuid4())
        with patch("web.views._api", side_effect=[(200, self.account), fresh]) as api:
            self.assertEqual(self.client.post(reverse("moderation-reports-assign", args=[self.target]), data).status_code, 400)
        self.assertNotIn("POST", [call.kwargs.get("method") for call in api.call_args_list])
        # An expired or tampered cache is ignored.
        session = self.client.session
        session["moderator_roster"] = {"at": 0, "people": {known: "Stale"}}
        session.save()
        third, api = self.open_detail(self.listing(), roster)
        self.assertEqual(api.call_count, 4)
