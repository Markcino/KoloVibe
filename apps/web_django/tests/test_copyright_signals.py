"""Decision E (D11-008): reviewers see copyright claim signals, never the claimant."""

from unittest.mock import patch

from django.test import TestCase

from .test_admin import AdminConsoleTests


class CopyrightSignalTests(TestCase):
    login = AdminConsoleTests.login
    record = AdminConsoleTests.record
    detail = AdminConsoleTests.detail
    detail_url = AdminConsoleTests.detail_url

    def setUp(self):
        AdminConsoleTests.setUp(self)

    def open(self, rights):
        self.login(role="moderator")
        detail = self.detail("reports") | {"copyright": rights}
        with patch("web.views._api", side_effect=[(200, self.account), (200, detail)]):
            return self.client.get(self.detail_url("reports"))

    def test_signals_are_shown_and_escaped(self):
        response = self.open({"work_reference": "<b>Original recording</b>", "claimant_verified": True,
                              "organisation": "Monrovia Records", "claimant_claims": 3, "claimant_dismissed": 1,
                              "creator_active_strikes": 2})
        self.assertContains(response, "Verified rights holder")
        self.assertContains(response, "&lt;b&gt;Original recording&lt;/b&gt;")
        self.assertContains(response, "3 in total, 1 dismissed")
        self.assertContains(response, "earlier upheld takedowns")

    def test_no_panel_without_a_copyright_record_and_bad_context_is_refused(self):
        self.assertNotContains(self.open(None), "Claim signals")
        response = self.open({"work_reference": None, "claimant_verified": False, "organisation": "Label",
                              "claimant_claims": None, "claimant_dismissed": None, "creator_active_strikes": None})
        self.assertEqual(response.status_code, 503)
