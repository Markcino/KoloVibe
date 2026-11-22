"""WEB-SEC / WEB-ADM scoped ASVS 5.0.0 L2 evidence; see tests/security/README.md."""
import json
from unittest.mock import patch, MagicMock
from uuid import uuid4
from django.test import TestCase
from . import test_admin as fixtures


class WebHardeningTests(TestCase):
    setUp = fixtures.AdminConsoleTests.setUp
    login = fixtures.AdminConsoleTests.login
    record = fixtures.AdminConsoleTests.record
    detail = fixtures.AdminConsoleTests.detail

    def assert_protections(self, response):
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")
        for directive in ("default-src 'none'", "script-src 'none'", "object-src 'none'", "base-uri 'none'", "frame-ancestors 'none'", "form-action 'self'"):
            self.assertIn(directive, response["Content-Security-Policy"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])

    def test_WEB_SEC_001_headers_and_cache_on_documents_redirects_and_errors(self):
        for path in ("/", "/login/", "/admin/account/", "/missing/", "/register/"):
            self.assert_protections(self.client.get(path))
        self.login()
        with patch("web.views._api", return_value=(200, self.account)):
            self.assert_protections(self.client.get("/admin/account/"))
        for status in (403, 404, 500, 503):
            with patch("web.views._api", side_effect=[(200, self.account), (status, {"detail": "private-host secret-token"})]):
                response = self.client.get("/admin/audit/")
            self.assert_protections(response)
            self.assertNotIn(b"secret-token", response.content)
            self.assertNotIn(b"private-host", response.content)

    def test_WEB_SEC_002_staging_transport_and_cookie_attributes(self):
        with self.settings(SESSION_COOKIE_NAME="__Host-kolovibe_session", SESSION_COOKIE_SECURE=True,
                           CSRF_COOKIE_SECURE=True, SECURE_HSTS_SECONDS=86400, SECURE_SSL_REDIRECT=False):
            self.login()
            cookie = self.client.cookies["__Host-kolovibe_session"]
            self.assertTrue(cookie["secure"])
            self.assertTrue(cookie["httponly"])
            self.assertEqual(cookie["path"], "/")
            self.assertEqual(cookie["domain"], "")
            self.assertEqual(cookie["samesite"], "Lax")
            self.assertNotIn(self.access, cookie.value)
            self.assertNotIn(self.refresh, cookie.value)
            response = self.client.get("/login/", secure=True)
            self.assertIn("max-age=86400", response["Strict-Transport-Security"])
            with self.settings(SECURE_SSL_REDIRECT=True):
                self.assertEqual(self.client_class().get("/login/").status_code, 301)

    def test_WEB_SEC_003_reviewer_history_is_autoescaped_and_preview_is_same_origin(self):
        self.login()
        value = self.detail("videos")
        value["video"]["description"] = '<img src=x onerror="alert(1)">'
        value["reports"] = [{"id": str(uuid4()), "video_id": self.target, "reason": "other", "details": "<script>report</script>", "status": "open", "created_at": "2026-11-21T10:00:00Z"}]
        value["decisions"] = [{"id": str(uuid4()), "action": "reject", "status": "applied", "reason": "<script>reason</script>", "created_at": "2026-11-21T10:00:00Z"}]
        value["preview"] = {"id": self.target, "url": "/api/v1/moderation/previews/" + self.target, "expires_at": "2026-11-21T10:01:00Z"}
        with patch("web.views._api", side_effect=[(200, self.account), (200, value)]):
            response = self.client.get(f"/admin/moderation/videos/{self.target}/")
        self.assertContains(response, "&lt;script&gt;report&lt;/script&gt;")
        self.assertContains(response, "&lt;script&gt;reason&lt;/script&gt;")
        self.assertNotContains(response, "<script>")
        self.assertContains(response, f'/admin/moderation/previews/{self.target}/')
        self.assertNotContains(response, "r2.cloudflarestorage.com")

    def test_WEB_SEC_004_logout_clears_client_state_and_get_is_not_mutating(self):
        self.login()
        with patch("web.views._api", return_value=(200, self.account)) as api:
            self.assertEqual(self.client.get("/admin/logout/").status_code, 405)
            api.assert_called_once()
        with patch("web.views._api", side_effect=[(200, self.account), (204, {})]):
            response = self.client.post("/admin/logout/")
        self.assertEqual(response["Clear-Site-Data"], '"cache", "cookies", "storage"')
        self.assert_protections(response)
        self.assertFalse(self.client.session.get("authenticated"))

    def test_WEB_SEC_005_staging_profile_hsts_csrf_cookie_and_single_csp_source(self):
        from pathlib import Path
        from django.conf import settings
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Strict")
        self.assertFalse(settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertFalse(settings.SECURE_HSTS_PRELOAD)
        nginx = Path(__file__).resolve().parents[3] / "infra/nginx/kolovibe-web-staging.conf"
        self.assertNotIn("add_header Content-Security-Policy", nginx.read_text())

    def test_WEB_ADM_006_mfa_pattern_is_valid_under_unicode_sets_flag(self):
        from django.template.loader import render_to_string
        from django.test import RequestFactory
        html = render_to_string("form.html", {"kind": "mfa", "title": "Verify your sign-in"}, RequestFactory().get("/login/mfa/"))
        self.assertIn(r"[A-Za-z0-9_\-]{32,128}", html)

    def test_WEB_ADM_001_bounded_unicode_detail_exceeding_64k_remains_valid(self):
        self.login()
        value = self.detail("videos")
        value["reports"] = [{"id": str(uuid4()), "video_id": self.target, "reason": "other", "details": "अ" * 2000,
                             "status": "open", "created_at": "2026-11-21T10:00:00Z"} for _ in range(20)]
        raw = json.dumps(value).encode()
        self.assertGreater(len(raw), 65536)
        identity, detail = MagicMock(), MagicMock()
        identity.status, identity.read.return_value = 200, json.dumps(self.account).encode()
        detail.status, detail.read.return_value = 200, raw
        with patch("web.views.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.side_effect = [identity, detail]
            response = self.client.get(f"/admin/moderation/videos/{self.target}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "अ")


    def test_WEB_ADM_005_cross_record_metadata_is_rejected(self):
        self.login()
        value = self.detail("videos")
        value["video"]["id"] = str(uuid4())
        with patch("web.views._api", side_effect=[(200, self.account), (200, value)]):
            self.assertEqual(self.client.get(f"/admin/moderation/videos/{self.target}/").status_code, 503)


    def test_WEB_ADM_004_entry_is_headerless_sign_in_and_navigation_marks_current_page(self):
        self.assertRedirects(self.client.get("/"), "/login/", fetch_redirect_response=False)
        page = self.client.get("/login/")
        self.assertNotContains(page, "<header")
        self.assertNotContains(page, "<nav")
        self.assertContains(page, "auth-card")
        self.login()
        self.assertRedirects(self.client.get("/"), "/login/", fetch_redirect_response=False)
        with patch("web.views._api", return_value=(200, self.account)):
            response = self.client.get("/admin/account/")
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'aria-label="Open navigation"')
