import secrets
import os
import subprocess
import sys
import uuid
from unittest.mock import patch
from urllib.request import ProxyHandler

from django.conf import settings
from django.test import Client, SimpleTestCase
from django.urls import reverse


class WebJourneys(SimpleTestCase):
    def test_liveness_does_not_depend_on_gateway(self):
        response = self.client.get(reverse("web-liveness"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_staging_refuses_missing_secret_mount(self):
        environment = dict(os.environ,
                           KOLOVIBE_ENV="staging", KOLOVIBE_GATEWAY_URL="http://127.0.0.1")
        environment.pop("KOLOVIBE_WEB_SECRET_KEY_FILE", None)
        result = subprocess.run([sys.executable, "-c", "import web.settings"],
                                cwd=settings.BASE_DIR, env=environment,
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Staging web requires its fixed secret mount", result.stderr)

    def test_gateway_request_uses_fixed_host_without_environment_proxy(self):
        from web.views import _NoRedirect, _api

        with patch("web.views.build_opener") as opener, \
             self.settings(GATEWAY_URL="http://127.0.0.1", GATEWAY_HOST="mobile-api.cabetechs.shop"):
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b"{}"
            self.assertEqual(_api("/videos"), (200, {}))
        self.assertIsInstance(opener.call_args.args[0], ProxyHandler)
        self.assertEqual(opener.call_args.args[0].proxies, {})
        self.assertIsInstance(opener.call_args.args[1], _NoRedirect)
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.get_header("Host"), "mobile-api.cabetechs.shop")
        self.assertEqual(request.full_url, "http://127.0.0.1/api/v1/videos")

    def test_staging_credentials_are_secure_and_host_only(self):
        from web.views import _clear_credentials, _set_credentials
        from django.http import HttpResponse

        with self.settings(CSRF_COOKIE_SECURE=True):
            response = HttpResponse()
            self.assertTrue(_set_credentials(response, {
                "access_token": "access", "refresh_token": "refresh"}))
            for cookie in response.cookies.values():
                self.assertTrue(cookie["secure"])
                self.assertTrue(cookie["httponly"])
                self.assertEqual(cookie["samesite"], "Strict")
                self.assertEqual(cookie["domain"], "")
            _clear_credentials(response)
            for cookie in response.cookies.values():
                self.assertEqual(cookie["max-age"], 0)
                self.assertTrue(cookie["secure"])

    def test_password_reset_request_keeps_account_state_private(self):
        with patch("web.views._api", return_value=(204, {})) as api:
            response = self.client.post(reverse("password-reset-request"),
                                        {"email": "viewer@example.test"})
        self.assertContains(response, "If your account is eligible")
        self.assertEqual(api.call_args.args, ("/auth/password/reset-request",))
        self.assertEqual(api.call_args.kwargs["data"], {"email": "viewer@example.test"})

    def test_successful_reset_and_change_clear_browser_credentials(self):
        self.client.cookies["kv_access"] = secrets.token_urlsafe(32)
        self.client.cookies["kv_refresh"] = secrets.token_urlsafe(48)
        with patch("web.views._api", return_value=(204, {})):
            response = self.client.post(reverse("password-reset"), {
                "code": secrets.token_urlsafe(48), "new_password": secrets.token_urlsafe(28),
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies["kv_access"]["max-age"], 0)
        self.assertEqual(response.cookies["kv_refresh"]["max-age"], 0)

        self.client.cookies["kv_access"] = secrets.token_urlsafe(32)
        self.client.cookies["kv_refresh"] = secrets.token_urlsafe(48)
        account = {"id": str(uuid.uuid4()), "email": "viewer@example.test", "display_name": "Viewer"}
        with patch("web.views._api", side_effect=[(200, account), (204, {})]) as api:
            response = self.client.post(reverse("password-change"), {
                "current_password": secrets.token_urlsafe(28),
                "new_password": secrets.token_urlsafe(28),
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(api.call_args.args, ("/me/password",))
        self.assertEqual(response.cookies["kv_access"]["max-age"], 0)
        self.assertEqual(response.cookies["kv_refresh"]["max-age"], 0)

    def test_profile_and_sessions_use_own_authenticated_gateway_paths(self):
        account_id = str(uuid.uuid4())
        account = {"id": account_id, "email": "viewer@example.test", "display_name": "Viewer"}
        self.client.cookies["kv_access"] = secrets.token_urlsafe(32)
        with patch("web.views._api", side_effect=[(200, account),
                (200, {**account, "display_name": "Updated"})]) as api:
            response = self.client.post(reverse("profile-edit"), {"display_name": "Updated"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(api.call_args.args, ("/me",))
        self.assertEqual(api.call_args.kwargs["method"], "PATCH")
        session_id = str(uuid.uuid4())
        page = {"items": [{"id": session_id, "created_at": "2026-11-11T00:00:00Z",
                           "expires_at": "2026-12-11T00:00:00Z", "current": False}]}
        with patch("web.views._api", side_effect=[(200, account), (200, page)]):
            response = self.client.get(reverse("sessions"))
        self.assertContains(response, "End session")
        self.assertNotIn(self.client.cookies["kv_access"].value, response.content.decode())
        with patch("web.views._api", side_effect=[(200, account), (204, {})]) as api:
            response = self.client.post(reverse("revoke-session", args=[session_id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(api.call_args.args, ("/me/sessions/" + session_id,))
        self.assertEqual(api.call_args.kwargs["method"], "DELETE")

    def test_csrf_blocks_session_revocation(self):
        client = Client(enforce_csrf_checks=True)
        with patch("web.views._api") as api:
            response = client.post(reverse("revoke-session", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 403)
        api.assert_not_called()

    def test_preferences_and_privacy_use_own_account_credentials(self):
        account = {"id": str(uuid.uuid4()), "email": "viewer@example.test", "display_name": "Viewer"}
        self.client.cookies["kv_access"] = secrets.token_urlsafe(32)
        with patch("web.views._api", side_effect=[(200, account), (200, {
                "email_notifications": True, "push_notifications": False})]) as api:
            response = self.client.post(reverse("preferences"), {"email_notifications": "on"})
        self.assertContains(response, "Email notifications")
        self.assertEqual(api.call_args.args, ("/me/preferences",))
        self.assertEqual(api.call_args.kwargs["data"], {
            "email_notifications": True, "push_notifications": False,
        })
        receipt = {"id": str(uuid.uuid4()), "kind": "deletion", "status": "received",
                   "created_at": "2026-11-11T12:00:00Z"}
        current_password = secrets.token_urlsafe(28)
        with patch("web.views._api", side_effect=[(200, account), (201, receipt)]) as api:
            response = self.client.post(reverse("privacy-requests"), {
                "kind": "deletion", "current_password": current_password,
            })
        self.assertContains(response, "request was received")
        self.assertNotIn(current_password, response.content.decode())
        self.assertEqual(api.call_args.kwargs["data"], {
            "kind": "deletion", "current_password": current_password,
        })

    def test_privacy_request_requires_csrf_and_rejects_unknown_kind(self):
        client = Client(enforce_csrf_checks=True)
        with patch("web.views._api") as api:
            response = client.post(reverse("privacy-requests"), {
                "kind": "deletion", "current_password": secrets.token_urlsafe(28),
            })
        self.assertEqual(response.status_code, 403)
        api.assert_not_called()
        account = {"id": str(uuid.uuid4()), "email": "viewer@example.test", "display_name": "Viewer"}
        self.client.cookies["kv_access"] = secrets.token_urlsafe(32)
        with patch("web.views._api", return_value=(200, account)) as api:
            response = self.client.post(reverse("privacy-requests"), {
                "kind": "withdrawal", "current_password": secrets.token_urlsafe(28),
            })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(api.call_count, 1)

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
                "id": str(uuid.uuid4()),
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
        self.assertRedirects(self.client.get(reverse("points")), reverse("login"),
                             fetch_redirect_response=False)

    def test_points_uses_creator_owned_gateway_response(self):
        creator = str(uuid.uuid4())
        self.client.cookies["kv_access"] = "session"

        def gateway(path, **kwargs):
            if path == "/me":
                return 200, {"id": str(uuid.uuid4()), "display_name": "Creator", "email": "c@example.test"}
            if path == "/creators/me/points":
                return 200, {"creator_id": creator, "balance": 3,
                             "currency": "POINTS", "as_of": "2026-11-11T12:00:00Z"}
            return 200, {"items": [{"id": str(uuid.uuid4()), "creator_id": creator,
                                    "amount": 3, "kind": "award", "rule_version": "DEC-003-v1",
                                    "created_at": "2026-11-11T12:00:00Z"}],
                         "next_cursor": None}

        with patch("web.views._api", side_effect=gateway):
            response = self.client.get(reverse("points"))
        self.assertContains(response, "3")
        self.assertContains(response, "Award", status_code=200)

    def test_public_creator_profile_uses_gateway_data(self):
        import uuid
        creator_id = uuid.uuid4()
        with patch("web.views._api", return_value=(200, {
                "id": str(creator_id),
                "handle": "original-voice", "bio": "", "status": "active"})):
            response = self.client.get(reverse("creator-detail", args=[creator_id]))
        self.assertContains(response, "@original-voice")

    def test_creator_page_never_renders_an_account_id(self):
        import uuid
        creator_id, account = uuid.uuid4(), uuid.uuid4()
        with patch("web.views._api", return_value=(200, {
                "id": str(creator_id), "user_id": str(account),
                "handle": "original-voice", "bio": "", "status": "active"})):
            response = self.client.get(reverse("creator-detail", args=[creator_id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, str(account))
