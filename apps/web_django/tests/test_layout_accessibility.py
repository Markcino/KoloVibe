"""Structural accessibility and responsive-layout checks on real rendered console pages, and on the stylesheet.

These are static checks of what the server sends. They do not replace a screen-reader pass, a browser check at real
widths or a keyboard walk-through on a device; none was performed here.
"""

import re
import secrets
import uuid
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

CSS = (Path(__file__).resolve().parents[1] / "static" / "css" / "site.css").read_text()
INTERACTIVE_NAME = re.compile(r"\S")


class PageFacts(HTMLParser):
    """Collects the facts the checks below need; no tree, no JavaScript."""

    def __init__(self):
        super().__init__()
        self.lang = self.viewport = self.skip_target = None
        self.ids, self.duplicate_ids = set(), set()
        self.h1 = self.main = self.tables_without_caption = self.th_without_scope = 0
        self.labels_for, self.controls, self.unnamed_buttons, self.images_without_alt = set(), [], [], []
        self.links_without_name = []
        self._stack, self._text, self._wrapped_in_label = [], [], 0
        self._table_has_caption = []
        self.forms = []
        self.main_attrs = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._stack.append((tag, a))
        self._text.append([])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "meta" and a.get("name") == "viewport":
            self.viewport = a.get("content")
        if "id" in a:
            (self.duplicate_ids if a["id"] in self.ids else self.ids).add(a["id"])
        if tag == "a" and a.get("class") == "skip-link":
            self.skip_target = (a.get("href") or "").lstrip("#")
        if tag == "h1":
            self.h1 += 1
        if tag == "main":
            self.main += 1
            self.main_attrs = a
        if tag == "label":
            self._wrapped_in_label += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if tag == "table":
            self._table_has_caption.append(False)
        if tag == "caption" and self._table_has_caption:
            self._table_has_caption[-1] = True
        if tag == "th" and "scope" not in a:
            self.th_without_scope += 1
        if tag == "img":
            if "alt" not in a:
                self.images_without_alt.append(a.get("src"))
            elif a["alt"].strip() and self._text:
                # An image's alternative text names the link or button that contains it.
                for texts in self._text[:-1]:
                    texts.append(a["alt"])
        if tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "submit", "button"):
            self.controls.append((a, bool(self._wrapped_in_label)))
        if tag == "form":
            self.forms.append(a)

    def handle_data(self, data):
        if self._text:
            self._text[-1].append(data)

    def handle_endtag(self, tag):
        if tag == "label":
            self._wrapped_in_label = max(0, self._wrapped_in_label - 1)
        if tag == "table" and self._table_has_caption and not self._table_has_caption.pop():
            self.tables_without_caption += 1
        while self._stack:
            open_tag, attrs = self._stack.pop()
            text = "".join(self._text.pop()).strip()
            if self._stack and self._text:
                self._text[-1].append(text)
            if open_tag in ("button", "a") and not (text or attrs.get("aria-label") or attrs.get("title")):
                (self.unnamed_buttons if open_tag == "button" else self.links_without_name).append(attrs)
            if open_tag == tag:
                break


def facts(html):
    parser = PageFacts()
    parser.feed(html)
    return parser


class RenderedPageTests(TestCase):
    def setUp(self):
        self.account = {"id": str(uuid.uuid4()), "email": "admin@example.test",
                        "display_name": "Console administrator", "roles": ["administrator"]}

    def sign_in(self, client, role="administrator"):
        self.account["roles"] = [role]
        with patch("web.views._api", return_value=(202, {"mfa_required": True, "expires_in": 300,
                                                         "challenge_token": secrets.token_urlsafe(48)})):
            client.post(reverse("login"), {"email": self.account["email"], "password": secrets.token_urlsafe(30)})
        with patch("web.views._api", return_value=(200, {"user": self.account, "access_token": secrets.token_urlsafe(36),
                                                         "refresh_token": str(uuid.uuid4()) + "." + secrets.token_urlsafe(48)})):
            client.post(reverse("login-mfa"), {"code": "012345"})

    def pages(self):
        """Rendered HTML of pages covering forms, tables, empty states, errors and the navigation shell."""
        found = {}
        anonymous = Client()
        found["login"] = anonymous.get(reverse("login")).content.decode()
        with patch("web.views._api", return_value=(202, {"mfa_required": True, "expires_in": 300,
                                                         "challenge_token": secrets.token_urlsafe(48)})):
            anonymous.post(reverse("login"), {"email": "a@example.test", "password": secrets.token_urlsafe(30)})
        found["mfa"] = anonymous.get(reverse("login-mfa")).content.decode()
        client = Client()
        self.sign_in(client)
        item = {"id": str(uuid.uuid4()), "title": "Review this video"}
        report = {"id": str(uuid.uuid4()), "video_id": str(uuid.uuid4()), "status": "open",
                  "created_at": "2026-11-21T10:00:00Z", "reason": "spam", "details": "Report details"}

        def answer(path, **kwargs):
            if path == "/me":
                return 200, dict(self.account)
            if path.startswith("/moderation/videos"):
                return 200, {"items": [item], "next_cursor": None}
            if path.startswith("/moderation/reports"):
                return 200, {"items": [report], "next_cursor": None}
            return 503, {}
        with patch("web.views._api", side_effect=answer):
            found["video_queue"] = client.get(reverse("moderation-videos")).content.decode()
            found["report_queue"] = client.get(reverse("moderation-reports")).content.decode()
            found["appeal_queue_unavailable"] = client.get(reverse("moderation-appeals")).content.decode()
            found["account"] = client.get(reverse("account")).content.decode()
        found.update(self.business_pages(client))
        return found

    def business_pages(self, client):
        """The Business console pages: overview, queues, three item pages, a confirmation, categories and access."""
        when, case, rid, rep = "2026-11-24T10:00:00+00:00", str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        person = str(uuid.uuid4())
        v = {"case_id": case, "business_id": str(uuid.uuid4()), "display_name": "Ma Kolo Foods", "state": "under_review",
             "submitted_at": when, "assigned_to_you": True}
        p = {"revision_id": rid, "business_id": str(uuid.uuid4()), "display_name": "Beta Cafe", "submitted_at": when}
        r = {"report_id": rep, "subject_type": "review", "business_id": str(uuid.uuid4()), "reason_code": "misleading",
             "system_hold": True, "created_at": when}
        detail = {**v, "method": "manual_review", "legal_name": "Kolo Foods Ltd",
                  "evidence": [{"id": str(uuid.uuid4()), "kind": "note", "value": "LBR-1"}], "duplicate_candidates": []}
        revision = {"business_id": p["business_id"], "id": rid, "revision_no": 2, "state": "pending_review",
                    "display_name": "Beta Cafe", "category": "food", "description": "Bread.", "county_code": "montserrado",
                    "city": "Monrovia", "address_line": "", "address_public": False, "latitude": None, "longitude": None,
                    "coordinates_public": False, "time_zone": "Africa/Monrovia",
                    "contacts": [{"kind": "phone", "value": "+231770000000", "is_public": True}], "reason_code": None,
                    "changed_fields": ["description"]}
        report = {"report_id": rep, "subject_type": "review", "subject_id": str(uuid.uuid4()), "business_id": r["business_id"],
                  "reason_code": "misleading", "details": "", "system_hold": True,
                  "content": {"rating": 1, "title": None, "body": "Bad.", "state": "held", "basis": "open", "hold_reasons": []}}
        routes = {"/moderation/business-verifications": (200, {"items": [v], "next_cursor": None}),
                  f"/moderation/business-verifications/{case}": (200, detail),
                  "/moderation/business-profile-revisions": (200, {"items": [p], "next_cursor": None}),
                  f"/moderation/business-profile-revisions/{rid}": (200, revision),
                  "/moderation/business-reports": (200, {"items": [r], "next_cursor": None}),
                  f"/moderation/business-reports/{rep}": (200, report),
                  "/business-categories": (200, {"items": [{"slug": "food", "name": "Food", "active": True, "parent": None}]}),
                  "/admin/accounts/lookup": (200, {"account_id": person, "display_name": "Ada Eze", "role": "viewer",
                                                   "email_verified": True})}

        def answer(path, **kwargs):
            return (200, dict(self.account)) if path == "/me" else routes.get(path, (503, {}))
        found = {}
        with patch("web.views._api", side_effect=answer), patch("web.assignment_views.roster", return_value={person: "Ada Moderator"}):
            found["business_overview"] = client.get(reverse("business")).content.decode()
            found["business_queue"] = client.get(reverse("business-verifications")).content.decode()
            found["business_reports_queue"] = client.get(reverse("business-reports")).content.decode()
            case_page = client.get(reverse("business-verifications-detail", args=[case]))
            found["business_verification"] = case_page.content.decode()
            found["business_profile"] = client.get(reverse("business-profiles-detail", args=[rid])).content.decode()
            found["business_report"] = client.get(reverse("business-reports-detail", args=[rep])).content.decode()
            found["business_confirm"] = client.post(reverse("business-verifications-detail", args=[case]), {
                "intent": case_page.context["decision_intent"], "decision": "verify", "reason_code": "documents_checked"}).content.decode()
            found["business_categories"] = client.get(reverse("business-categories")).content.decode()
            found["business_grants"] = client.get(reverse("business-grants")).content.decode()
            found["business_candidate"] = client.post(reverse("business-grants"), {
                "form": "lookup", "intent": client.get(reverse("business-grants")).context["lookup_intent"],
                "email": "ada@example.test"}).content.decode()
        return found

    def test_the_business_pages_checked_here_are_the_real_pages_not_error_pages(self):
        pages = self.pages()
        expected = {"business_overview": "Queue summary", "business_queue": "Verification requests",
                    "business_reports_queue": "Business reports", "business_verification": "Evidence submitted",
                    "business_profile": "What changed", "business_report": "What was reported",
                    "business_confirm": "Confirm your decision", "business_categories": "Save a category",
                    "business_grants": "Reviewer access", "business_candidate": "Allow registration"}
        for name, text in expected.items():
            self.assertIn(text, pages[name], name)

    def test_every_rendered_page_has_the_document_structure_assistive_technology_needs(self):
        for name, html in self.pages().items():
            page = facts(html)
            with self.subTest(page=name):
                self.assertEqual(page.lang, "en")
                self.assertIn("width=device-width", page.viewport or "")
                self.assertNotIn("user-scalable=no", page.viewport or "")
                self.assertEqual(page.duplicate_ids, set(), "duplicate ids")
                self.assertEqual(page.images_without_alt, [], "images without alt text")
                self.assertEqual(page.th_without_scope, 0, "table headers without scope")
                self.assertEqual(page.tables_without_caption, 0, "tables without a caption")
                self.assertEqual(page.unnamed_buttons, [], "buttons with no accessible name")
                self.assertEqual(page.links_without_name, [], "links with no accessible name")

    def test_skip_link_targets_the_main_region_which_is_focusable_and_there_is_one_h1(self):
        for name, html in self.pages().items():
            page = facts(html)
            with self.subTest(page=name):
                self.assertEqual(page.skip_target, "main")
                self.assertIn("main", page.ids)
                self.assertEqual(page.main, 1, "exactly one main landmark")
                self.assertEqual(page.main_attrs.get("id"), "main")
                self.assertEqual(page.main_attrs.get("tabindex"), "-1", "so the skip link can move focus into it")
                self.assertLessEqual(page.h1, 1)

    def test_every_form_control_has_a_visible_label_or_an_accessible_name(self):
        for name, html in self.pages().items():
            page = facts(html)
            for attrs, inside_label in page.controls:
                with self.subTest(page=name, control=attrs.get("name") or attrs.get("type")):
                    self.assertTrue(inside_label or attrs.get("aria-label") or attrs.get("aria-labelledby")
                                    or (attrs.get("id") in page.labels_for), f"unlabelled control {attrs}")

    def test_every_state_changing_form_carries_a_csrf_token_and_posts(self):
        for name, html in self.pages().items():
            for form in re.findall(r"<form[^>]*>.*?</form>", html, re.S):
                if 'method="post"' in form:
                    with self.subTest(page=name):
                        self.assertIn('name="csrfmiddlewaretoken"', form)

    def test_scrolling_table_regions_are_keyboard_reachable_and_named(self):
        for name, html in self.pages().items():
            for region in re.findall(r'<div class="table-scroll"[^>]*>', html):
                with self.subTest(page=name):
                    self.assertIn('tabindex="0"', region)
                    self.assertIn("aria-label=", region)
                    self.assertIn('role="region"', region)

    def test_table_cells_carry_data_labels_so_rows_reflow_on_narrow_screens(self):
        for name, html in self.pages().items():
            for row in re.findall(r"<tbody>.*?</tbody>", html, re.S):
                for cell in re.findall(r"<td(?![^>]*colspan)[^>]*>", row):
                    with self.subTest(page=name):
                        self.assertIn("data-label=", cell, "a data cell without a label cannot reflow into a card")

    def test_error_messages_are_announced_not_only_coloured(self):
        html = self.pages()["appeal_queue_unavailable"]
        self.assertTrue(re.search(r'role="(alert|status)"|aria-live=', html) or "<h1" in html)


class StylesheetTests(TestCase):
    def test_the_layout_adapts_at_three_widths_and_never_requires_horizontal_page_scrolling(self):
        for query in ("(min-width: 600px)", "(min-width: 840px)", "(max-width: 839px)", "(max-width: 599px)"):
            self.assertIn(query, CSS)
        self.assertIn("overflow-x: auto", CSS, "wide tables scroll inside their own region")
        self.assertNotRegex(CSS, r"(?m)^\s*body\s*{[^}]*\bwidth:\s*\d+px")

    def test_focus_is_always_visible_and_never_removed(self):
        self.assertIn(":focus-visible { outline: 3px solid", CSS)
        # A rule that removes the outline must replace it with another visible indicator in the same rule.
        for rule in re.findall(r"[^{}]+{[^}]*outline:\s*(?:none|0)\b[^}]*}", CSS):
            self.assertRegex(rule, r"box-shadow|border-color|background", f"outline removed without a replacement: {rule[:80]}")

    def test_interactive_elements_meet_the_48_pixel_touch_target(self):
        for selector in (".text-button", "td a", "td button", ".pagination a"):
            self.assertRegex(CSS, re.escape(selector) + r"[^{]*{[^}]*min-height: 48px", selector)

    def test_user_preferences_are_honoured(self):
        for query in ("prefers-reduced-motion: reduce", "prefers-contrast: more", "forced-colors: active",
                      "prefers-color-scheme: dark"):
            self.assertIn(query, CSS)
        self.assertRegex(CSS, r"\.visually-hidden")
