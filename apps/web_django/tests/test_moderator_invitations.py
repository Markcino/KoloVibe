import json
import secrets
import uuid
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

import pyotp
import segno

from django.test import Client, TestCase
from django.utils import timezone

from tests import test_admin
from web import invitation_views


class ModeratorInvitationWebTests(TestCase):
    setUp = test_admin.AdminConsoleTests.setUp
    login = test_admin.AdminConsoleTests.login

    def page(self):
        return {"items": [{"id": self.target, "display_name": "<script>alert(1)</script>",
                          "email_masked": "r***@example.test", "status": "pending",
                          "expires_at": (timezone.now() + timedelta(hours=24)).isoformat()}], "next_cursor": None}

    def team(self, client=None):
        with patch("web.views._api", side_effect=[(200, self.account), (200, self.page())]):
            return (client or self.client).get("/admin/team/")

    def setup(self, client=None):
        client = client or self.client
        self.invite_code = secrets.token_urlsafe(48)
        self.secret = pyotp.random_base32()
        with patch("web.views._api", return_value=(200, {"secret": self.secret,
                   "expires_at": (timezone.now() + timedelta(minutes=5)).isoformat()})):
            return client.post("/moderator-invitation/", {"email": "reviewer@example.test",
                "invitation_code": self.invite_code, "password": secrets.token_urlsafe(32)})

    def test_admin_form_is_escaped_and_submission_uses_bound_idempotency_intent(self):
        self.login()
        page = self.team()
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(page, "<script>")
        self.assertIn("no-store", page.headers["Cache-Control"])
        proof = page.context["intent"]
        data = {"id": self.target, "status": "pending", "expires_at": (timezone.now() + timedelta(hours=24)).isoformat()}
        with patch("web.views._api", side_effect=[(200, self.account), (202, data)]) as api:
            response = self.client.post("/admin/team/", {"operation": "create", "intent": proof,
                "email": "reviewer@example.test", "display_name": "Reviewer", "reason": "Pilot moderation team"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(api.call_args.args, ("/admin/moderator-invitations",))
        self.assertIn("idempotency_key", api.call_args.kwargs)
        self.assertNotIn("role", api.call_args.kwargs["data"])

    def accepted_page(self, *names):
        rows = [{"id": str(uuid.uuid4()), "display_name": name, "email_masked": "m***@example.test", "status": "accepted",
                 "expires_at": (timezone.now() + timedelta(hours=1)).isoformat(), "account_id": str(uuid.uuid4())} for name in names]
        return rows, {"items": rows, "next_cursor": None}

    def test_team_lists_moderators_with_open_assignment_counts(self):
        self.login()
        rows, page = self.accepted_page("Ada Eze", "Bola Ade")
        ids = sorted(row["account_id"] for row in rows)
        summary = {"items": [{"moderator_id": ids[0], "videos": 1, "reports": 2, "appeals": 0},
                             {"moderator_id": ids[1], "videos": 0, "reports": 0, "appeals": 0}]}
        with patch("web.views._api", side_effect=[(200, self.account), (200, page), (200, summary)]) as api:
            response = self.client.get("/admin/team/")
        self.assertContains(response, "Moderators")
        self.assertContains(response, "3 open")
        self.assertContains(response, "1 videos · 2 reports · 0 appeals")
        self.assertContains(response, "None yet")
        self.assertEqual(api.call_args.args[0], "/admin/moderation/assignments/summary?" + "&".join(f"moderator={i}" for i in ids))

    def test_directory_degrades_when_workload_is_unavailable_or_malformed(self):
        self.login()
        rows, page = self.accepted_page("Ada Eze")
        for reply in ((503, {}), (200, {"items": [], "extra": 1}),
                      (200, {"items": [{"moderator_id": rows[0]["account_id"], "videos": -1, "reports": 0, "appeals": 0}]})):
            with patch("web.views._api", side_effect=[(200, self.account), (200, page), reply]):
                response = self.client.get("/admin/team/")
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Unavailable")
            self.assertContains(response, "Ada Eze")
        # No accepted moderators means no workload request at all.
        with patch("web.views._api", side_effect=[(200, self.account), (200, self.page())]) as api:
            self.assertNotContains(self.client.get("/admin/team/"), "Directory")
        self.assertEqual(api.call_count, 2)

    def test_invitation_code_and_email_are_cleaned_before_use(self):
        code = secrets.token_urlsafe(48)
        pasted = code[:20] + " \r\n " + code[20:] + "  "
        with patch("web.views._api", return_value=(200, {"secret": pyotp.random_base32(),
                   "expires_at": (timezone.now() + timedelta(minutes=5)).isoformat()})) as api:
            self.client.post("/moderator-invitation/", {"email": "  reviewer@example.test ", "invitation_code": pasted,
                                                         "password": secrets.token_urlsafe(32)})
        sent = api.call_args.kwargs["data"]
        self.assertEqual((sent["invitation_code"], sent["email"]), (code, "reviewer@example.test"))

    def test_cross_session_intent_and_missing_csrf_are_rejected(self):
        self.login()
        proof = self.team().context["intent"]
        other = Client()
        self.login(client=other)
        with patch("web.views._api", return_value=(200, self.account)) as api:
            self.assertEqual(other.post("/admin/team/", {"operation": "create", "intent": proof}).status_code, 400)
            self.assertEqual(api.call_count, 1)
        client = Client(enforce_csrf_checks=True)
        with patch("web.views._api") as api:
            self.assertEqual(client.post("/moderator-invitation/", {}).status_code, 403)
            api.assert_not_called()

    def test_identity_denies_moderators_including_direct_team_url(self):
        self.login("moderator")
        with patch("web.views._api", side_effect=[(200, self.account), (403, {})]) as api:
            response = self.client.get("/admin/team/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(api.call_args.args, ("/admin/moderator-invitations",))

    def test_setup_proof_is_encrypted_and_qr_is_session_bound(self):
        response = self.setup()
        self.assertEqual(response.status_code, 302)
        state = dict(self.client.session)
        self.assertIn(invitation_views.PENDING, state)
        for secret in (self.invite_code, self.secret):
            self.assertNotIn(secret, json.dumps(state))
            self.assertNotIn(secret, response.headers["Location"])
        page = self.client.get("/moderator-invitation/")
        self.assertNotContains(page, self.secret)
        self.assertNotContains(page, self.invite_code)
        self.assertContains(page, 'src="/moderator-invitation/qr/"')
        self.assertIn("no-store", page.headers["Cache-Control"])
        self.assertIn("script-src 'none'", page.headers["Content-Security-Policy"])

        with patch("web.invitation_views.segno.make_qr", wraps=segno.make_qr) as make_qr:
            qr = self.client.get("/moderator-invitation/qr/")
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr["Content-Type"], "image/png")
        self.assertTrue(qr.content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("no-store", qr.headers["Cache-Control"])
        uri = urlsplit(make_qr.call_args.args[0])
        self.assertEqual((uri.scheme, uri.netloc), ("otpauth", "totp"))
        self.assertEqual(unquote(uri.path), "/KoloVibe:reviewer@example.test")
        params = parse_qs(uri.query)
        self.assertEqual(params["secret"], [self.secret])
        self.assertEqual(params["issuer"], ["KoloVibe"])
        self.assertEqual(params["algorithm"], ["SHA1"])
        self.assertEqual(params["digits"], ["6"])
        self.assertEqual(params["period"], ["30"])

    def test_completion_shows_recovery_codes_once_without_creating_login(self):
        self.setup()
        codes = [secrets.token_urlsafe(32) for _ in range(10)]
        with patch("web.views._api", return_value=(200, {"enrolled": True, "recovery_codes": codes})) as api:
            page = self.client.post("/moderator-invitation/", {"code": "123456"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, codes[0])
        self.assertNotIn("authenticated", self.client.session)
        self.assertNotIn(invitation_views.PENDING, self.client.session)
        self.assertNotContains(self.client.get("/moderator-invitation/"), codes[0])
        self.assertEqual(api.call_args.kwargs["data"], {"email": "reviewer@example.test",
            "invitation_code": self.invite_code, "code": "123456"})

    def test_tampered_expired_or_wrong_response_state_fails_closed(self):
        self.setup()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=6)):
            self.assertNotContains(self.client.get("/moderator-invitation/"), self.secret)
            self.assertEqual(self.client.get("/moderator-invitation/qr/").status_code, 404)
        with patch("web.views._api", return_value=(200, {"secret": self.secret, "expires_at": "bad"})):
            self.assertEqual(self.client.post("/moderator-invitation/", {}).status_code, 503)
        self.assertNotIn(invitation_views.PENDING, self.client.session)

    def test_anonymous_invitee_is_not_public_signup_and_team_needs_login(self):
        self.assertEqual(self.client.get("/moderator-invitation/").status_code, 200)
        self.assertEqual(self.client.get("/moderator-invitation/qr/").status_code, 404)
        self.assertEqual(self.client.post("/moderator-invitation/qr/", {}).status_code, 405)
        self.assertEqual(self.client.get("/admin/team/").status_code, 302)
        self.assertEqual(self.client.get("/register/").status_code, 404)
        self.assertContains(self.client.get("/login/"), "Accept moderator invitation")
