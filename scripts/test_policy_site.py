"""The static policies page (Decision B, owner ruling "Policies page only"): same words as the API, nothing active."""
import html
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXTS = ROOT / "services" / "identity" / "service" / "legal_texts"
sys.path.insert(0, str(ROOT / "scripts"))

import build_policy_site as site  # noqa: E402


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.text, self.attributes = [], [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes += [name for name, _ in attrs]
        self.urls += [value for name, value in attrs if name in ("href", "src", "action") and value]

    def handle_data(self, data):
        self.text.append(data)


class PolicySiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_policy_site.py"), str(cls.out)], check=True,
                       capture_output=True, timeout=120)
        cls.pages = {p.relative_to(cls.out).as_posix(): p.read_text() for p in cls.out.rglob("*.html")}

    def parse(self, name):
        parser = Tags()
        parser.feed(self.pages[name])
        return parser

    def test_exactly_the_index_terms_privacy_and_deletion_pages_and_one_stylesheet(self):
        self.assertEqual(set(self.pages),
                         {"index.html", "terms/index.html", "privacy/index.html", "delete-account/index.html"})
        self.assertEqual({p.name for p in self.out.iterdir() if p.is_file()}, {"index.html", "policies.css"})

    def test_nothing_active_and_nothing_external(self):
        for name in self.pages:
            with self.subTest(name):
                parsed = self.parse(name)
                self.assertFalse({"script", "form", "input", "iframe", "img", "object", "embed", "button"}
                                 & set(parsed.tags))
                for url in parsed.urls:
                    self.assertFalse(re.match(r"^[a-z]+:|^//", url), url)
                self.assertIn(site.CSP, html.unescape(self.pages[name]))
                self.assertFalse([a for a in parsed.attributes if a.startswith("on")], "no event handlers")

    def test_each_page_shows_the_identity_text_its_version_and_the_pending_review_banner(self):
        for kind in ("terms", "privacy"):
            with self.subTest(kind):
                source = next(TEXTS.glob(f"{kind}-*.md"))
                version = source.stem.split("-", 1)[1]
                page = self.pages[f"{kind}/index.html"]
                text = " ".join(self.parse(f"{kind}/index.html").text)
                self.assertIn("Draft pending legal review.", text)
                self.assertIn(f"Version {version}", text)
                for line in source.read_text().splitlines():
                    words = re.sub(r"^#+ |^- |\*\*", "", line).strip()
                    if words:
                        self.assertIn(words, " ".join(text.split()), f"missing from the page: {words[:60]}")
                self.assertNotIn("<p>#", page)

    def test_the_deletion_page_names_the_app_and_both_ways_to_ask(self):
        # Owner ruling, 26 November: Google Play needs a deletion request resource outside the app that names it.
        text = " ".join(" ".join(self.parse("delete-account/index.html").text).split())
        self.assertIn("Delete your KoloVibe account", text)
        self.assertIn("Draft pending legal review.", text)
        self.assertIn("Go to Settings, then Delete account.", text)
        self.assertIn("Without the app", text)
        self.assertNotIn("form", self.parse("delete-account/index.html").tags)
        for line in site.DELETION.read_text().splitlines():
            words = re.sub(r"^#+ |^- |\*\*", "", line).strip()
            if words:
                self.assertIn(words, text)
        for name in self.pages:
            with self.subTest(name):
                self.assertIn("delete-account/", self.pages[name], "every page links the deletion page")

    def test_markup_in_a_text_is_escaped(self):
        rendered = site.render_markdown("# <b>x</b>\n\nA & **<script>alert(1)</script>**\n- <img src=x>")
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;script&gt;", rendered)


if __name__ == "__main__":
    unittest.main()
