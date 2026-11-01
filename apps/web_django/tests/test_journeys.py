import secrets
import uuid
from unittest.mock import patch

from django.test import Client, SimpleTestCase
from django.urls import reverse


class WebJourneys(SimpleTestCase):
    def test_feed_paginates_and_preserves_creator_filter(self):
        creator = str(uuid.uuid4())
        items = [{"id": str(uuid.uuid4()), "creator_id": creator, "title": "Original",
                  "description": "", "state": "published"} for _ in range(20)]
        with patch("web.views._api", return_value=(200, {
                "items": items, "next_cursor": items[-1]["id"]})):
            response = self.client.get(reverse("feed"), {"creator_id": creator})
        self.assertContains(response, "Next page")
        self.assertContains(response, items[-1]["id"])
        with patch("web.views._api", return_value=(200, {
                "items": [], "next_cursor": None})) as call:
            response = self.client.get(reverse("feed"), {
                "creator_id": creator, "cursor": items[-1]["id"]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("cursor=" + items[-1]["id"], call.call_args.args[0])

    def test_invalid_filter_and_malformed_page_never_render_success(self):
        with patch("web.views._api") as call:
            self.assertEqual(self.client.get(reverse("feed"), {"cursor": "../me"}).status_code, 400)
            call.assert_not_called()
        for payload in ({"items": [{}], "next_cursor": None},
                        {"items": [], "next_cursor": "bad"}, {"items": []}):
            with self.subTest(payload=payload), patch("web.views._api", return_value=(200, payload)):
                self.assertEqual(self.client.get(reverse("feed")).status_code, 503)

    def test_mismatched_creator_detail_is_unavailable(self):
        with patch("web.views._api", return_value=(200, {
                "id": str(uuid.uuid4()), "user_id": str(uuid.uuid4()),
                "handle": "someone", "bio": "", "status": "active"})):
            self.assertEqual(self.client.get(
                reverse("creator-detail", args=[uuid.uuid4()])).status_code, 503)

    def test_account_outage_does_not_consume_refresh_token(self):
        self.client.cookies["kv_access"] = secrets.token_urlsafe(32)
        self.client.cookies["kv_refresh"] = secrets.token_urlsafe(48)
        with patch("web.views._api", return_value=(503, {})) as call:
            response = self.client.get(reverse("account"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(call.call_count, 1)
        self.assertNotIn("kv_refresh", response.cookies)

    def test_rotated_credentials_survive_following_account_outage(self):
        self.client.cookies["kv_access"] = secrets.token_urlsafe(32)
        self.client.cookies["kv_refresh"] = secrets.token_urlsafe(48)
        rotated = {"access_token": secrets.token_urlsafe(32),
                   "refresh_token": secrets.token_urlsafe(48)}
        with patch("web.views._api", side_effect=[(401, {}), (200, rotated), (503, {})]):
            response = self.client.get(reverse("account"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.cookies["kv_refresh"].value, rotated["refresh_token"])
        self.assertNotIn(rotated["refresh_token"], response.content.decode())

    def test_logout_outage_clears_cookies_and_reports_unconfirmed_revocation(self):
        self.client.cookies["kv_refresh"] = secrets.token_urlsafe(48)
        with patch("web.views._api", return_value=(503, {})):
            response = self.client.post(reverse("logout"))
        self.assertContains(response, "could not be confirmed", status_code=503)
        self.assertEqual(response.cookies["kv_access"]["max-age"], 0)
        self.assertEqual(response.cookies["kv_refresh"]["max-age"], 0)

    def test_login_preserves_throttle_and_privilege_denial(self):
        for status in (403, 429):
            with self.subTest(status=status), patch("web.views._api", return_value=(status, {})):
                self.assertEqual(self.client.post(reverse("login")).status_code, status)

    def test_empty_feed_is_real_empty_state(self):
        with patch("web.views._api", return_value=(200, {"items": [], "next_cursor": None})):
            response = self.client.get(reverse("feed"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No originals are available yet")

    def test_feed_dependency_failure_is_visible(self):
        with patch("web.views._api", return_value=(503, {"detail": "Service unavailable"})):
            response = self.client.get(reverse("feed"))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "temporarily unavailable", status_code=503)

    def test_login_cookie_is_http_only_and_never_rendered(self):
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(48)
        password = secrets.token_urlsafe(24)
        with patch("web.views._api", return_value=(200, {
                "access_token": access, "refresh_token": refresh})):
            response = self.client.post(reverse("login"), {"email": "user@example.test",
                                                           "password": password})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.cookies["kv_access"]["httponly"])
        self.assertTrue(response.cookies["kv_refresh"]["httponly"])
        self.assertNotIn(access, response.content.decode())
        self.assertNotIn(refresh, response.content.decode())

    def test_csrf_blocks_cross_site_account_post(self):
        client = Client(enforce_csrf_checks=True)
        with patch("web.views._api") as call:
            response = client.post(reverse("login"), {"email": "user@example.test"})
        self.assertEqual(response.status_code, 403)
        call.assert_not_called()

    def test_expired_session_redirects_to_sign_in(self):
        response = self.client.get(reverse("account"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)

    def test_creator_and_points_are_gated(self):
        self.assertEqual(self.client.get(reverse("creator")).status_code, 503)
        self.assertEqual(self.client.get(reverse("points")).status_code, 503)

    def test_public_creator_profile_uses_gateway_data(self):
        import uuid
        creator_id = uuid.uuid4()
        with patch("web.views._api", return_value=(200, {
                "id": str(creator_id), "user_id": str(uuid.uuid4()),
                "handle": "original-voice", "bio": "", "status": "active"})):
            response = self.client.get(reverse("creator-detail", args=[creator_id]))
        self.assertContains(response, "@original-voice")
