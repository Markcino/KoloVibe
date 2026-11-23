"""Design-system guardrails: colour contrast, CSP-safe markup and basic accessibility structure.

These run without a browser so every change is checked in CI. They complement, not replace, a manual look.
"""

import re
import uuid
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from tests import test_admin

CSS = (Path(settings.BASE_DIR) / "static" / "css" / "site.css").read_text()


def _tokens(block):
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\b", block))


def _luminance(colour):
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + .05) / (lo + .05)


TEXT_PAIRS = [("md-on-primary", "md-primary"), ("md-on-primary-container", "md-primary-container"),
              ("md-on-secondary-container", "md-secondary-container"), ("md-on-error", "md-error"),
              ("md-on-error-container", "md-error-container"), ("md-on-surface", "md-surface"),
              ("md-on-surface", "md-surface-container"), ("md-on-surface-variant", "md-surface"),
              ("md-on-surface-variant", "md-surface-container"), ("md-on-surface-variant", "md-surface-low"),
              ("md-on-surface-variant", "md-surface-highest"), ("md-primary", "md-surface"),
              ("md-primary", "md-surface-container"), ("tone-purple-fg", "tone-purple-bg"),
              ("tone-amber-fg", "tone-amber-bg"), ("tone-teal-fg", "tone-teal-bg"),
              ("tone-neutral-fg", "tone-neutral-bg"), ("tone-success-fg", "tone-success-bg"),
              ("md-inverse-on-surface", "md-inverse-surface")]


class ColourTokenTests(SimpleTestCase):
    def schemes(self):
        light = _tokens(CSS[CSS.index(":root {"):CSS.index("@media (prefers-color-scheme: dark)")])
        dark = _tokens(CSS[CSS.index("@media (prefers-color-scheme: dark) {"):CSS.index("/* ---------- 2. Base")])
        return {"light": light, "dark": {**light, **dark}}

    def test_every_text_pair_meets_wcag_aa_in_both_schemes(self):
        for name, tokens in self.schemes().items():
            for fg, bg in TEXT_PAIRS:
                self.assertGreaterEqual(contrast(tokens[fg], tokens[bg]), 4.5, f"{name}: {fg} on {bg}")

    def test_control_outlines_meet_3_to_1_against_their_surfaces(self):
        for name, tokens in self.schemes().items():
            for surface in ("md-surface", "md-surface-container"):
                self.assertGreaterEqual(contrast(tokens["md-outline"], tokens[surface]), 3.0, f"{name}: outline on {surface}")

    def test_stylesheet_loads_nothing_remote_and_respects_user_preferences(self):
        self.assertNotRegex(CSS, r"@import|url\(\s*['\"]?(https?:)?//")
        for rule in ("prefers-reduced-motion", "prefers-color-scheme: dark", "forced-colors", "prefers-contrast"):
            self.assertIn(rule, CSS)


class _Structure(HTMLParser):
    """Collects what a screen-reader and the CSP care about."""

    def __init__(self):
        super().__init__()
        self.headings, self.problems, self.label_depth = [], [], 0
        self.label_for, self.ids, self.fields = set(), [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self.problems.append("script element")
        if "style" in a:
            self.problems.append(f"inline style on <{tag}>")
        if any(name.startswith("on") for name in a):
            self.problems.append(f"event handler on <{tag}>")
        for name in ("href", "src", "action"):
            if a.get(name, "").startswith(("http://", "https://", "//")):
                self.problems.append(f"external {name}: {a[name]}")
        if tag == "img" and "alt" not in a:
            self.problems.append("img without alt")
        if tag == "label":
            self.label_depth += 1
            if "for" in a:
                self.label_for.add(a["for"])
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if "id" in a:
            self.ids.append(a["id"])
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            self.fields.append((self.label_depth > 0, a.get("id"), a.get("aria-label")))

    def handle_endtag(self, tag):
        if tag == "label":
            self.label_depth -= 1


def inspect(html):
    parser = _Structure()
    parser.feed(html)
    problems = list(parser.problems)
    if parser.headings.count(1) != 1:
        problems.append(f"expected one h1, found {parser.headings.count(1)}")
    if any(b - a > 1 for a, b in zip(parser.headings, parser.headings[1:])):
        problems.append(f"heading levels skip: {parser.headings}")
    if len(parser.ids) != len(set(parser.ids)):
        problems.append("duplicate ids")
    problems += [f"unlabelled field {field}" for field in parser.fields
                 if not (field[0] or field[2] or field[1] in parser.label_for)]
    return problems


class RenderedPageStructureTests(TestCase):
    setUp = test_admin.AdminConsoleTests.setUp
    login = test_admin.AdminConsoleTests.login
    record = test_admin.AdminConsoleTests.record
    detail = test_admin.AdminConsoleTests.detail
    routes = staticmethod(test_admin.AdminConsoleTests.routes)

    def check(self, name, response):
        self.assertEqual(inspect(response.content.decode()), [], name)

    def test_public_and_error_pages(self):
        for path in ("/login/", "/moderator-invitation/", "/no-such-page/"):
            self.check(path, self.client.get(path))

    def test_creator_pages(self):
        import uuid as _uuid
        self.login("administrator")
        row = {"account_id": str(_uuid.uuid4()), "status": "pending", "creator_id": str(_uuid.uuid4()), "handle": "ada_eze",
               "submitted_at": "2026-11-23T10:00:00+00:00"}
        page = (200, {"items": [row], "next_cursor": None})
        with patch("web.views._api", side_effect=[(200, self.account), page]):
            response = self.client.get("/admin/creators/")
        self.check("creators", response)
        found = (200, {"account_id": str(_uuid.uuid4()), "display_name": "Ada Eze", "role": "viewer", "email_verified": False})
        with patch("web.views._api", side_effect=[(200, self.account), found, page]):
            self.check("creator candidate", self.client.post("/admin/creators/", {"operation": "lookup", "email": "ada@example.test"}))
        intent = response.context["applications"][0]["intent"]
        with patch("web.views._api", side_effect=[(200, self.account)]):
            self.check("creator confirm", self.client.post("/admin/creators/", {
                "operation": "decide", "account_id": row["account_id"], "handle": "ada_eze", "decision": "rejected", "intent": intent}))

    def test_console_pages_for_both_roles(self):
        totals = {"videos": {"review": 1, "published": 2, "rejected": 3, "removed": 4},
                  "reports": {"open": 1, "resolved": 2, "dismissed": 3}, "appeals": {"open": 1, "denied": 2, "restored": 3}}
        holds = {"total": 0, "items": [], "next_cursor": None}
        for role in ("administrator", "moderator"):
            self.login(role)
            table = {"/me": (200, self.account), "/moderation/totals": (200, totals), "/engagement/fraud-holds": (200, holds),
                     "/admin/audit": (200, {"items": [], "next_cursor": None})}
            with patch("web.views._api", side_effect=self.routes(table)):
                self.check(f"{role} dashboard", self.client.get("/admin/"))
            with patch("web.views._api", side_effect=self.routes({**table, "/moderation/totals": (403, {"detail": "Resource unavailable"})})):
                self.check(f"{role} dashboard", self.client.get("/admin/"))
            with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [self.record("reports")], "next_cursor": None})]):
                self.check(f"{role} queue", self.client.get("/admin/moderation/reports/"))
            replies = [(200, self.account), (200, self.detail("reports"))]
            if role == "administrator":
                replies += [(200, {"scope": "reports", "target_id": self.target, "items": []}), (503, {})]
            with patch("web.views._api", side_effect=replies):
                self.check(f"{role} review", self.client.get(f"/admin/moderation/reports/{self.target}/"))
            with patch("web.views._api", side_effect=[(200, self.account), (200, self.account)]):
                self.check(f"{role} account", self.client.get("/admin/account/"))
            with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [], "next_cursor": None})]):
                self.check(f"{role} audit", self.client.get("/admin/audit/"))
