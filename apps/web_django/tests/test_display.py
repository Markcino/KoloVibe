"""Readable values: relative ages, UTC clock times and human labels."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from tests import test_admin
from web.templatetags.admin_display import age, human_label, utc_clock


class DisplayFilterTests(SimpleTestCase):
    def test_age_is_relative_bounded_and_safe(self):
        now = timezone.now()
        self.assertEqual(age((now - timedelta(days=3, hours=2)).isoformat()), "3 days ago")
        self.assertEqual(age((now - timedelta(minutes=5, seconds=10)).isoformat()), "5 minutes ago")
        self.assertEqual(age((now + timedelta(hours=1)).isoformat()), "just now")
        for bad in (None, "", "yesterday", "2026-11-21T10:00:00"):
            self.assertEqual(age(bad), "")

    def test_clock_and_labels(self):
        self.assertEqual(utc_clock("2026-11-23T14:32:10+01:00"), "13:32 UTC")
        self.assertEqual(utc_clock("2026-11-23T14:32:10"), "")
        self.assertEqual(human_label("not_reversed"), "Not reversed")


class QueueReadabilityTests(TestCase):
    setUp = test_admin.AdminConsoleTests.setUp
    login = test_admin.AdminConsoleTests.login

    def test_report_queue_shows_reason_excerpt_and_age_instead_of_raw_ids(self):
        self.login("moderator")
        stamp = (timezone.now() - timedelta(days=2, hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        item = {"id": self.target, "video_id": str(uuid.uuid4()), "status": "open", "created_at": stamp,
                "reason": "harassment", "details": "x" * 200}
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [item], "next_cursor": None})]):
            response = self.client.get("/admin/moderation/reports/")
        self.assertContains(response, "Harassment")
        self.assertContains(response, "2 days ago")
        self.assertContains(response, "…")
        self.assertNotContains(response, "x" * 200)
        self.assertContains(response, self.target[:8])
        self.assertContains(response, f'href="/admin/moderation/reports/{self.target}/"')
