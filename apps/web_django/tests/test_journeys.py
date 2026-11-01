import secrets
from unittest.mock import patch

from django.test import Client, SimpleTestCase
from django.urls import reverse


class WebJourneys(SimpleTestCase):
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
