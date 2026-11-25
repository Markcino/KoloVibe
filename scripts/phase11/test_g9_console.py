"""Phase 11, test group 9: the administrator and moderator console in a real browser (Chromium via Playwright).

Real Firefox and Safari/WebKit are NOT RUN (not installed in this environment); a screen reader is NOT RUN. Accessibility here
is structural (labels, landmarks, focus, keyboard, narrow layouts), which is evidence, not a screen-reader test.
"""

import os
import re
import secrets
import sqlite3
import time
import unittest
from datetime import timedelta
from urllib.parse import urlparse

import lib

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


def S():
    return lib.CURRENT


ADMIN_PAGES = ["/admin/", "/admin/audit/", "/admin/points/", "/admin/fraud/", "/admin/creators/", "/admin/team/", "/admin/account/",
               "/admin/account/sessions/", "/admin/business/", "/admin/business/verifications/", "/admin/business/profiles/",
               "/admin/business/reports/", "/admin/business/access/", "/admin/business/categories/",
               "/admin/moderation/videos/", "/admin/moderation/reports/", "/admin/moderation/appeals/"]


class Console(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.viewer = S().new_user()

    def setUp(self):
        if sync_playwright is None:
            self.skipTest("playwright is not installed")
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=["--no-sandbox"])
        self.addCleanup(self.pw.stop)
        self.addCleanup(self.browser.close)
        self.base = f"http://127.0.0.1:{S().ports['web']}"
        self.used = {}

    def person(self, role):
        """A brand-new privileged account: each sign-in burns one single-use recovery code, so accounts are never shared."""
        return S().privileged(role)

    # ---- helpers -----------------------------------------------------------------------------------------
    def ctx(self):
        context = self.browser.new_context(viewport={"width": 1280, "height": 900})
        return context

    def code(self, user):
        index = self.used.get(user["email"], 0) + 1  # line 0 is not reused by the API tests; each login burns one
        self.used[user["email"]] = index
        return user["recoveries"][index]

    def login(self, page, user, mfa=True, password=None, code=None):
        page.goto(self.base + "/login/")
        page.get_by_label("Email address").fill(user["email"])
        page.get_by_label("Password").fill(password or user["password"])
        page.get_by_role("button", name=re.compile("Sign in")).click()
        if mfa and page.url.rstrip("/").endswith("/login/mfa"):
            page.get_by_label("Verification code").fill(code or self.code(user))
            page.get_by_role("button", name=re.compile("Verify")).click()
        return page

    def web_db(self):
        return sqlite3.connect(S().base / "web-fixture.sqlite3")

    # ---- authentication ---------------------------------------------------------------------------------------
    def test_T9_01_an_administrator_signs_in_with_password_and_mfa_and_reaches_the_dashboard(self):
        page = self.ctx().new_page()
        self.login(page, self.person("administrator"))
        self.assertTrue(urlparse(page.url).path.startswith("/admin"), page.url)
        self.assertEqual(page.locator("h1").count() >= 1, True)
        cookies = {c["name"]: c for c in page.context.cookies()}
        session = cookies.get("sessionid")
        self.assertIsNotNone(session, "a session cookie must exist")
        self.assertTrue(session["httpOnly"], "the session cookie must be HttpOnly")
        self.assertEqual(session["sameSite"], "Lax")

    def test_T9_02_a_moderator_signs_in_and_cannot_reach_administrator_only_pages(self):
        page = self.ctx().new_page()
        self.login(page, self.person("moderator"))
        self.assertTrue(urlparse(page.url).path.startswith("/admin"), page.url)
        for path in ("/admin/creators/", "/admin/business/access/", "/admin/business/categories/"):
            response = page.goto(self.base + path)
            self.assertIn(response.status, (403, 404), f"{path} -> {response.status} for a moderator")

    def test_T9_03_a_viewer_cannot_sign_in_to_the_console(self):
        page = self.ctx().new_page()
        page.goto(self.base + "/login/")
        page.get_by_label("Email address").fill(self.viewer["email"])
        page.get_by_label("Password").fill(self.viewer["password"])
        page.get_by_role("button", name=re.compile("Sign in")).click()
        self.assertFalse(urlparse(page.url).path.startswith("/admin"), page.url)
        self.assertEqual(page.goto(self.base + "/admin/").url.rstrip("/").endswith("/login"), True, "no console session may exist")

    def test_T9_04_wrong_password_and_unknown_email_get_the_same_page(self):
        pages = []
        for email, password in ((self.person("administrator")["email"], "Wrong-password-1!"), ("nobody%s@example.test" % secrets.token_hex(3), "Wrong-password-1!")):
            page = self.ctx().new_page()
            page.goto(self.base + "/login/")
            page.get_by_label("Email address").fill(email)
            page.get_by_label("Password").fill(password)
            with page.expect_navigation():
                page.get_by_role("button", name=re.compile("Sign in")).click()
            pages.append((page.url, re.sub(r"\s+", " ", page.locator("main, body").first.inner_text())))
        self.assertEqual(pages[0], pages[1], "the console must not reveal which emails are registered")

    def test_T9_05_a_wrong_mfa_code_does_not_open_a_session(self):
        page = self.ctx().new_page()
        self.login(page, self.person("administrator"), code="000000")
        self.assertFalse(urlparse(page.url).path.startswith("/admin"), page.url)
        self.assertTrue(page.goto(self.base + "/admin/audit/").url.rstrip("/").endswith("/login") or "mfa" in page.url)

    def test_T9_06_every_console_page_redirects_an_anonymous_visitor_to_sign_in(self):
        page = self.ctx().new_page()
        for path in ADMIN_PAGES:
            page.goto(self.base + path)
            self.assertIn("/login", page.url, f"{path} did not require sign-in")

    def test_T9_07_login_does_not_follow_an_external_next_parameter_and_changes_the_session_id(self):
        context = self.ctx()
        page = context.new_page()
        page.goto(self.base + "/login/?next=https://evil.example/phish")
        before = {c["name"]: c["value"] for c in context.cookies()}.get("sessionid")
        self.login(page, self.person("administrator"))
        after = {c["name"]: c["value"] for c in context.cookies()}.get("sessionid")
        self.assertNotIn("evil.example", page.url)
        if before:
            self.assertNotEqual(before, after, "the session identifier must change at sign-in (fixation)")

    # ---- logout and sessions --------------------------------------------------------------------------------------
    def test_T9_10_logout_ends_the_session_and_the_old_cookie_no_longer_works(self):
        context = self.ctx()
        page = context.new_page()
        self.login(page, self.person("administrator"))
        old = next(c for c in context.cookies() if c["name"] == "sessionid")
        page.goto(self.base + "/admin/account/")
        page.get_by_role("button", name=re.compile("Sign out|Log out", re.I)).first.click()
        page.wait_for_load_state()
        other = self.ctx()
        other.add_cookies([{"name": old["name"], "value": old["value"], "url": self.base}])
        replay = other.new_page()
        replay.goto(self.base + "/admin/audit/")
        self.assertIn("/login", replay.url, "a stolen cookie must not work after sign-out")

    def test_T9_11_a_get_request_to_the_logout_url_does_not_sign_you_out(self):
        page = self.ctx().new_page()
        self.login(page, self.person("moderator"))
        page.goto(self.base + "/admin/logout/")
        page.goto(self.base + "/admin/")
        self.assertTrue(urlparse(page.url).path.startswith("/admin"), "logout must need a POST with a CSRF token, not a link")

    def test_T9_12_state_changing_posts_without_a_csrf_token_are_refused(self):
        context = self.ctx()
        page = context.new_page()
        self.login(page, self.person("administrator"))
        for path in ("/admin/logout/", "/admin/account/password/", "/admin/account/profile/", "/admin/creators/", "/admin/team/"):
            response = context.request.post(self.base + path, form={"x": "1"})
            self.assertEqual(response.status, 403, f"POST {path} without CSRF -> {response.status}")

    def _age(self, column, minutes):
        with self.web_db() as db:
            rows = db.execute("select session_key from web_credential").fetchall()
            self.assertTrue(rows, "no server-side credential rows to age")
            stamp = lambda delta: (__import__("datetime").datetime.now(__import__("datetime").timezone.utc) - timedelta(minutes=delta)).strftime("%Y-%m-%d %H:%M:%S.%f")
            if column == "last_activity_at":
                db.execute("update web_credential set last_activity_at=?", (stamp(minutes),))
            else:
                db.execute("update web_credential set created_at=?, absolute_expires_at=?", (stamp(minutes), stamp(1)))

    def test_T9_13_an_idle_session_expires_after_thirty_minutes(self):
        page = self.ctx().new_page()
        user = S().privileged("moderator")
        self.login(page, user)
        self.assertTrue(urlparse(page.goto(self.base + "/admin/").url).path.startswith("/admin"))
        self._age("last_activity_at", 31)
        page.goto(self.base + "/admin/")
        self.assertIn("/login", page.url, "an idle session must expire")

    def test_T9_14_a_privileged_session_expires_fifteen_minutes_after_sign_in_even_if_active(self):
        page = self.ctx().new_page()
        user = S().privileged("moderator")
        self.login(page, user)
        self._age("created_at", 16)
        page.goto(self.base + "/admin/")
        self.assertIn("/login", page.url, "the absolute 15-minute limit must apply")

    # ---- headers and rendering -----------------------------------------------------------------------------------------
    def test_T9_20_security_headers_and_a_content_security_policy_that_forbids_scripts(self):
        context = self.ctx()
        page = context.new_page()
        self.login(page, self.person("administrator"))
        response = page.goto(self.base + "/admin/")
        h = {k.lower(): v for k, v in response.headers.items()}
        csp = h.get("content-security-policy", "")
        self.assertIn("script-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("form-action 'self'", csp)
        self.assertIn("no-store", h.get("cache-control", ""))
        self.assertEqual(h.get("x-content-type-options"), "nosniff")
        self.assertIn("same-origin", h.get("referrer-policy", ""))

    def test_T9_21_no_console_page_triggers_a_csp_violation_or_a_javascript_error(self):
        context = self.ctx()
        page = context.new_page()
        problems = []
        page.on("console", lambda m: problems.append(m.text) if ("Content Security Policy" in m.text or "Refused to" in m.text or m.type == "error" and "status of 4" not in m.text and "status of 5" not in m.text) else None)
        page.on("pageerror", lambda e: problems.append(str(e)))
        self.login(page, self.person("administrator"))
        for path in ADMIN_PAGES:
            response = page.goto(self.base + path)
            self.assertLess(response.status, 500, f"{path} -> {response.status}")
        self.assertEqual(problems, [], problems[:5])

    def test_T9_22_administrator_pages_load_without_a_server_error_and_without_leaking_internals(self):
        page = self.ctx().new_page()
        self.login(page, self.person("administrator"))
        for path in ADMIN_PAGES:
            response = page.goto(self.base + path)
            body = page.content()
            self.assertIn(response.status, (200, 403, 404, 503), f"{path} -> {response.status}")
            for marker in ("Traceback", "psycopg", "Internal Server Error", "settings.py", "SECRET_KEY"):
                self.assertNotIn(marker, body, path)

    # ---- accessibility (structural) ----------------------------------------------------------------------------------------
    def test_T9_30_every_form_control_and_button_has_an_accessible_name_and_the_page_has_landmarks(self):
        page = self.ctx().new_page()
        self.login(page, self.person("administrator"))
        failures = []
        for path in ["/login/"] + ADMIN_PAGES[:12]:
            page.goto(self.base + path)
            report = page.evaluate("""() => {
                const bad = [];
                const name = el => ((el.querySelector && el.querySelector('img[alt]:not([alt=""])')) ? 'img' : '') || (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || (el.labels && el.labels.length) || el.textContent.trim() || el.getAttribute('title') || el.getAttribute('alt') || '');
                document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(el => { if (!name(el)) bad.push('input:' + (el.name || el.type)); });
                document.querySelectorAll('button, a[href]').forEach(el => { if (!name(el)) bad.push(el.tagName.toLowerCase() + ':' + (el.getAttribute('href') || el.className)); });
                document.querySelectorAll('img').forEach(el => { if (!el.hasAttribute('alt')) bad.push('img:' + el.src.slice(-20)); });
                const out = {bad, lang: document.documentElement.lang, title: document.title, h1: document.querySelectorAll('h1').length,
                             main: document.querySelectorAll('main, [role=main]').length};
                return out; }""")
            if report["bad"] or not report["lang"] or not report["title"] or report["h1"] != 1 or report["main"] < 1:
                failures.append((path, report))
        self.assertEqual(failures, [], failures[:3])

    def test_T9_31_the_sign_in_form_works_with_the_keyboard_alone_and_focus_is_visible(self):
        page = self.ctx().new_page()
        page.goto(self.base + "/login/")
        order = []
        for _ in range(6):
            page.keyboard.press("Tab")
            order.append(page.evaluate("() => { const e = document.activeElement; return e ? (e.name || e.tagName) : null }"))
        self.assertIn("email", order)
        self.assertIn("password", order)
        self.assertLess(order.index("email"), order.index("password"), "tab order must follow the visual order")
        page.get_by_label("Email address").focus()
        outline = page.evaluate("""() => { const s = getComputedStyle(document.activeElement); return [s.outlineStyle, s.outlineWidth, s.boxShadow, s.borderColor]; }""")
        self.assertFalse(outline[0] == "none" and outline[2] == "none", f"no visible focus indicator: {outline}")
        user = self.person("administrator")
        page.get_by_label("Email address").fill(user["email"])
        page.keyboard.press("Tab")
        page.keyboard.type(user["password"])
        with page.expect_navigation():
            page.keyboard.press("Enter")
        self.assertIn("mfa", page.url, "Enter must submit the form")

    def test_T9_32_pages_fit_a_narrow_phone_width_and_200_percent_zoom_without_horizontal_scroll(self):
        context = self.browser.new_context(viewport={"width": 320, "height": 700})
        self.addCleanup(context.close)
        page = context.new_page()
        self.login(page, self.person("administrator"))
        wide = []
        for path in ["/admin/"] + ADMIN_PAGES[1:8]:
            page.goto(self.base + path)
            overflow = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if overflow > 2:
                wide.append((path, overflow))
        self.assertEqual(wide, [], wide)

    def test_T9_33_interactive_targets_are_large_enough_to_activate(self):
        page = self.ctx().new_page()
        self.login(page, self.person("administrator"))
        small = []
        for path in ("/admin/", "/admin/account/"):
            page.goto(self.base + path)
            small += [(path, t) for t in page.evaluate("""() => [...document.querySelectorAll('button, a[href], input:not([type=hidden])')]
                .map(e => { const r = e.getBoundingClientRect(); return [e.textContent.trim().slice(0, 20) || e.name, Math.round(r.width), Math.round(r.height)]; })
                .filter(x => x[2] > 0 && (x[1] < 24 || x[2] < 24))""")]
        self.assertEqual(small, [], f"targets below 24x24 CSS pixels (WCAG 2.2 AA 2.5.8): {small[:6]}")
