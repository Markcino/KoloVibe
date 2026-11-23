"""Fraud review: the full, scoped, read-only list of active holds."""

import secrets
import uuid
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse



def hold(number, video=None):
    return {"id": str(uuid.UUID(int=number + 1)), "video_id": video or str(uuid.uuid4()),
            "reason_code": "VELOCITY_ANOMALY", "created_at": "2026-11-21T10:00:00Z"}


class FraudReviewTests(TestCase):
    def setUp(self):
        self.account = {"id": str(uuid.uuid4()), "email": "admin@example.test",
                        "display_name": "Console administrator", "roles": ["administrator"]}
        self.access = secrets.token_urlsafe(36)
        self.refresh = str(uuid.uuid4()) + "." + secrets.token_urlsafe(48)

    def sign_in(self, role):
        self.account["roles"] = [role]
        with patch("web.views._api", return_value=(202, {"mfa_required": True,
                                                         "challenge_token": secrets.token_urlsafe(48), "expires_in": 300})):
            self.client.post(reverse("login"), {"email": self.account["email"], "password": secrets.token_urlsafe(30)})
        with patch("web.views._api", return_value=(200, {"user": self.account, "access_token": self.access,
                                                         "refresh_token": self.refresh})):
            self.assertEqual(self.client.post(reverse("login-mfa"), {"code": "012345"}).status_code, 302)

    def get(self, role, answers, path=None):
        """`answers` is what the gateway returns for /engagement/fraud-holds (status, body); /me is the account."""
        calls = []

        def fake(request_path, **kwargs):
            if request_path == "/me":
                return 200, dict(self.account, roles=[role])
            calls.append(request_path)
            return answers
        with patch("web.views._api", side_effect=fake):
            return self.client.get(path or reverse("fraud")), calls

    def test_an_administrator_sees_the_first_page_with_links_to_each_video_review_and_a_next_link(self):
        self.sign_in("administrator")
        items = [hold(number) for number in range(20)]
        response, calls = self.get("administrator", (200, {"total": 45, "items": items, "next_cursor": items[-1]["id"]}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ["/engagement/fraud-holds"])
        text = response.content.decode()
        self.assertIn("45 active holds", text)
        self.assertEqual(text.count("Open video review"), 20)
        self.assertIn(reverse("moderation-videos-detail", args=[items[0]["video_id"]]), text)
        self.assertIn(f'rel="next" href="?cursor={items[-1]["id"]}"', text)
        self.assertIn("Velocity anomaly", text)
        self.assertNotIn("First page", text)

    def test_the_cursor_is_validated_forwarded_and_only_the_cursor_is_accepted(self):
        self.sign_in("administrator")
        cursor = str(uuid.uuid4())
        response, calls = self.get("administrator", (200, {"total": 1, "items": [], "next_cursor": None}),
                                   reverse("fraud") + f"?cursor={cursor}")
        self.assertEqual(calls, [f"/engagement/fraud-holds?cursor={cursor}"])
        self.assertContains(response, "First page")
        for bad in ("?cursor=not-an-id", f"?cursor={cursor}&cursor={cursor}", f"?cursor={cursor}&status=open", "?q=1"):
            with self.subTest(bad=bad):
                response, calls = self.get("administrator", (200, {}), reverse("fraud") + bad)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(calls, [], "an invalid request never reaches the gateway")

    def test_malformed_or_inconsistent_gateway_data_is_refused_not_rendered(self):
        self.sign_in("administrator")
        good = hold(1)
        for body in ({"total": 1, "items": [dict(good, extra="x")], "next_cursor": None},
                     {"total": 1, "items": [dict(good, video_id="not-a-uuid")], "next_cursor": None},
                     {"total": 0, "items": [good], "next_cursor": None},
                     {"total": 3, "items": [], "next_cursor": None},
                     {"total": 1, "items": [good], "next_cursor": "something"}):
            with self.subTest(body=body):
                response, _ = self.get("administrator", (200, body))
                self.assertEqual(response.status_code, 503)
                self.assertNotIn(good["video_id"], response.content.decode())

    def test_gateway_refusals_and_outages_are_shown_as_errors_not_empty_lists(self):
        self.sign_in("administrator")
        for status, expected in ((403, 403), (404, 404), (429, 429), (500, 503), (503, 503)):
            with self.subTest(status=status):
                response, _ = self.get("administrator", (status, {"detail": "internal"}))
                self.assertEqual(response.status_code, expected)
                self.assertNotContains(response, "No active fraud holds", status_code=expected)

    def test_a_moderator_with_nothing_assigned_sees_the_explicit_empty_state_only_for_that_refusal(self):
        self.sign_in("moderator")
        response, _ = self.get("moderator", (403, {"detail": "Request unavailable"}))
        self.assertContains(response, "No review assignments yet")
        response, _ = self.get("moderator", (403, {"detail": "something else"}))
        self.assertEqual(response.status_code, 403)

    def test_an_administrator_never_gets_the_unassigned_empty_state(self):
        self.sign_in("administrator")
        response, _ = self.get("administrator", (403, {"detail": "Request unavailable"}))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "No review assignments yet", status_code=403)

    def test_the_page_is_read_only_and_never_cached(self):
        self.sign_in("administrator")
        response, _ = self.get("administrator", (200, {"total": 1, "items": [hold(1)], "next_cursor": None}))
        self.assertNotIn("<form", response.content.decode().split("<main", 1)[-1])
        self.assertIn("no-store", response["Cache-Control"])
        with patch("web.views._api", return_value=(200, dict(self.account))):
            self.assertEqual(self.client.post(reverse("fraud")).status_code, 405)

    def test_it_is_linked_from_navigation_for_both_roles(self):
        for role in ("administrator", "moderator"):
            self.client = Client()
            self.sign_in(role)
            response, _ = self.get(role, (200, {"total": 0, "items": [], "next_cursor": None}))
            self.assertContains(response, f'href="{reverse("fraud")}"')
            self.assertContains(response, 'aria-current="page"')
