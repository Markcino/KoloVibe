"""Admin-only boundaries, queue contracts, mutations, and failure states."""

import secrets
import uuid
from unittest.mock import patch
from urllib.error import URLError

from django.core import signing
from django.test import Client, TestCase
from django.urls import reverse

from web import staging_session
from web.api_contracts import ACTIONS, valid_queue_page
from web.models import WebCredential


class AdminConsoleTests(TestCase):
    def setUp(self):
        self.account = {"id": str(uuid.uuid4()), "email": "admin@example.test",
                        "display_name": "Console administrator", "roles": ["administrator"]}
        self.access = secrets.token_urlsafe(36)
        self.refresh = str(uuid.uuid4()) + "." + secrets.token_urlsafe(48)
        self.target = str(uuid.uuid4())

    def login(self, role="administrator", client=None):
        client = client or self.client
        self.account["roles"] = [role]
        with patch("web.views._api", return_value=(202, {
                "mfa_required": True, "challenge_token": secrets.token_urlsafe(48), "expires_in": 300})):
            client.post(reverse("login"), {"email": self.account["email"], "password": secrets.token_urlsafe(30)})
        with patch("web.views._api", return_value=(200, {
                "user": self.account, "access_token": self.access, "refresh_token": self.refresh})):
            response = client.post(reverse("login-mfa"), {"code": "012345"})
        self.assertEqual(response.status_code, 302)

    def paths(self):
        return ["/admin/", "/admin/points/", "/admin/audit/", "/admin/account/",
                "/admin/account/profile/", "/admin/account/password/", "/admin/account/sessions/",
                f"/admin/account/sessions/{self.target}/revoke/", "/admin/logout/"] + [
                    path for kind in ACTIONS for path in (
                        f"/admin/moderation/{kind}/", f"/admin/moderation/{kind}/{self.target}/")]

    def record(self, kind, target=None):
        target = target or self.target
        if kind == "videos":
            return {"id": target, "title": "Review this video"}
        return {"id": target, "video_id": self.target, "status": "open",
                "created_at": "2026-11-21T10:00:00Z", "reason": "spam" if kind == "reports" else "Please review my appeal.",
                **({"details": "Report details"} if kind == "reports" else {})}

    def page(self, kind):
        return {"items": [self.record(kind)], "next_cursor": None}

    def detail_url(self, kind, target=None):
        return reverse(f"moderation-{kind}-detail", args=[target or self.target])

    def intent(self, kind, client=None):
        with patch("web.views._api", side_effect=[(200, self.account), (200, self.page(kind))]):
            response = (client or self.client).get(self.detail_url(kind))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.client.session.session_key.encode(), response.content)
        return response.context["intent"]

    def test_removed_public_routes_are_404_for_get_and_post(self):
        for path in ["/videos/" + self.target + "/", "/creators/" + self.target + "/",
                     "/register/", "/verify/", "/password/reset-request/", "/password/reset/",
                     "/account/", "/account/profile/", "/account/password/", "/account/sessions/",
                     "/account/sessions/" + self.target + "/revoke/", "/account/preferences/",
                     "/account/privacy/", "/creator/", "/points/", "/logout/"]:
            for method in (self.client.get, self.client.post):
                with self.subTest(path=path, method=method.__name__), patch("web.views._api") as api:
                    self.assertEqual(method(path).status_code, 404)
                    api.assert_not_called()
        self.assertRedirects(self.client.get("/"), "/login/", fetch_redirect_response=False)
        self.login()
        self.assertRedirects(self.client.get("/"), "/admin/", fetch_redirect_response=False)

    def test_all_admin_routes_require_login_even_posts(self):
        for path in self.paths():
            for method in (self.client.get, self.client.post):
                with self.subTest(path=path, method=method.__name__), patch("web.views._api") as api:
                    self.assertRedirects(method(path), "/login/", fetch_redirect_response=False)
                    api.assert_not_called()

    def test_nonprivileged_and_unknown_roles_denied_on_every_admin_route(self):
        for role in ("viewer", "creator", "support", "finance", "service_worker", "unknown"):
            for path in self.paths():
                self.login()
                with self.subTest(role=role, path=path), patch("web.views._api", return_value=(200, {
                        **self.account, "roles": [role]})) as api:
                    self.assertEqual(self.client.post(path).status_code, 403)
                    self.assertEqual(api.call_count, 1)
                self.assertFalse(WebCredential.objects.exists())

    def test_roles_use_gateway_authorized_queues(self):
        for role in ("moderator", "administrator"):
            self.login(role)
            for path in ("/admin/", "/admin/account/", "/admin/audit/",
                         "/admin/account/profile/", "/admin/account/password/"):
                with patch("web.views._api", return_value=(200, self.account)):
                    self.assertEqual(self.client.get(path).status_code, 200)
            for kind in ACTIONS:
                with patch("web.views._api", side_effect=[(200, self.account), (200, self.page(kind))]):
                    response = self.client.get(reverse(f"moderation-{kind}"))
                self.assertEqual(response.status_code, 200)
            with patch("web.views._api", return_value=(200, self.account)):
                self.assertEqual(self.client.get("/admin/points/").status_code, 200 if role == "administrator" else 403)

    def test_mfa_cannot_be_bypassed_by_password_response_or_browser_cookie(self):
        for role in ("administrator", "moderator", "viewer", "creator", "support"):
            with patch("web.views._api", side_effect=[(200, {
                    "user": {**self.account, "roles": [role]}, "access_token": self.access,
                    "refresh_token": self.refresh}), (204, {})]) as api:
                self.assertEqual(self.client.post("/login/", {"email": self.account["email"],
                                                        "password": secrets.token_urlsafe(30)}).status_code, 403)
                self.assertEqual(api.call_args.args, ("/auth/logout",))
            self.assertFalse(WebCredential.objects.exists())
        self.client.cookies["kv_access"] = self.access
        self.client.cookies["kv_refresh"] = self.refresh
        self.assertRedirects(self.client.get("/admin/"), "/login/", fetch_redirect_response=False)
        self.login()
        session = self.client.session
        session.pop("mfa_verified")
        session.save()
        with patch("web.views._api", return_value=(200, self.account)):
            self.assertRedirects(self.client.get("/admin/"), "/login/?expired=1", fetch_redirect_response=False)
        self.assertFalse(WebCredential.objects.exists())

    def test_decisions_use_existing_actions_endpoints_and_stable_idempotency_keys(self):
        self.login()
        for kind, actions in ACTIONS.items():
            for action in actions:
                intent = self.intent(kind)
                submitted = {"intent": intent, "action": action, "reason": "Reviewed against the content policy."}
                result = {"id": str(uuid.uuid4()), "video_id": self.target, "action": action, "status": "applied"}
                keys = []
                for _ in range(2):
                    with patch("web.views._api", side_effect=[(200, self.account), (200, result)]) as api:
                        response = self.client.post(self.detail_url(kind), submitted)
                    self.assertContains(response, "Decision recorded")
                    self.assertEqual(api.call_args.args, (f"/moderation/{kind}/{self.target}/decisions",))
                    self.assertEqual(api.call_args.kwargs["method"], "POST")
                    self.assertEqual(api.call_args.kwargs["token"], self.access)
                    self.assertEqual(api.call_args.kwargs["data"], {
                        "action": action, "reason": submitted["reason"]})
                    keys.append(api.call_args.kwargs["idempotency_key"])
                self.assertEqual(keys[0], keys[1])
                self.assertGreaterEqual(len(keys[0]), 16)

    def test_decision_intent_binds_actor_session_kind_target_and_expiry(self):
        self.login()
        intent = self.intent("videos")
        for changed in ({"actor": str(uuid.uuid4())}, {"session": "other-session"},
                        {"kind": "reports"}, {"target": str(uuid.uuid4())}, {"key": "invalid"}):
            payload = signing.loads(intent, salt="admin-decision")
            payload.update(changed)
            tampered = signing.dumps(payload, salt="admin-decision")
            with patch("web.views._api", return_value=(200, self.account)) as api:
                self.assertEqual(self.client.post(self.detail_url("videos"), {
                    "intent": tampered, "action": "publish", "reason": "A valid review reason."}).status_code, 400)
                self.assertEqual(api.call_count, 1)
        with patch("web.views._api", return_value=(200, self.account)) as api, \
                patch("django.core.signing.time.time", return_value=0):
            expired = signing.dumps(signing.loads(intent, salt="admin-decision"), salt="admin-decision")
        with patch("web.views._api", return_value=(200, self.account)) as api:
            self.assertEqual(self.client.post(self.detail_url("videos"), {
                "intent": expired, "action": "publish", "reason": "A valid review reason."}).status_code, 400)
            api.assert_called_once()

    def test_decisions_revalidate_role_and_reject_invalid_submissions_without_mutation(self):
        self.login()
        intent = self.intent("videos")
        for data in ({}, {"intent": intent, "action": "payout", "reason": "A valid review reason."},
                     {"intent": intent, "action": "publish", "reason": "short"},
                     {"intent": intent + "tampered", "action": "publish", "reason": "A valid review reason."}):
            with patch("web.views._api", return_value=(200, self.account)) as api:
                self.assertEqual(self.client.post(self.detail_url("videos"), data).status_code, 400)
                self.assertEqual(api.call_count, 1)
        with patch("web.views._api", return_value=(200, {**self.account, "roles": ["support"]})) as api:
            self.assertEqual(self.client.post(self.detail_url("videos"), {
                "intent": intent, "action": "publish", "reason": "A valid review reason."}).status_code, 403)
            self.assertEqual(api.call_count, 1)

    def test_csrf_enforced_on_every_decision_and_mutation(self):
        self.login()
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.client.cookies
        for path in [self.detail_url(kind) for kind in ACTIONS] + ["/admin/logout/", "/admin/account/password/",
                "/admin/account/profile/", f"/admin/account/sessions/{self.target}/revoke/"]:
            with patch("web.views._api") as api:
                response = client.post(path, {})
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, "CSRF", status_code=403)
                api.assert_not_called()
        for kind in ACTIONS:
            intent = self.intent(kind, client)
            action = sorted(ACTIONS[kind])[0]
            with patch("web.views._api", side_effect=[(200, self.account), (200, {
                    "id": str(uuid.uuid4()), "video_id": self.target, "action": action, "status": "applied"})]):
                response = client.post(self.detail_url(kind), {"intent": intent, "action": action,
                    "reason": "A valid review reason.", "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
            self.assertEqual(response.status_code, 200)

    def test_queue_cursor_forwarding_validation_and_status_filter(self):
        self.login()
        for kind in ACTIONS:
            ids = sorted(str(uuid.uuid4()) for _ in range(21))
            page = {"items": [self.record(kind, item_id) for item_id in ids[:20]], "next_cursor": ids[19]}
            with patch("web.views._api", side_effect=[(200, self.account), (200, page)]):
                response = self.client.get(reverse(f"moderation-{kind}"))
            self.assertContains(response, "Next page")
            self.assertIn(ids[19], response.context["next_query"])
            with patch("web.views._api", side_effect=[(200, self.account), (200, {
                    "items": [self.record(kind, ids[20])], "next_cursor": None})]) as api:
                response = self.client.get(reverse(f"moderation-{kind}"), {"cursor": ids[19]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(api.call_args.args, (f"/moderation/{kind}?cursor={ids[19]}",))
            for query in ("?cursor=bad", "?cursor=x&cursor=y", "?status=closed", "?actor_id=" + self.target,
                          "?status=open&status=open"):
                with patch("web.views._api", return_value=(200, self.account)) as api:
                    self.assertEqual(self.client.get(reverse(f"moderation-{kind}") + query).status_code, 400)
                    self.assertEqual(api.call_count, 1)

    def test_malformed_queue_records_and_cursor_cycles_are_never_rendered(self):
        self.login()
        for kind in ACTIONS:
            good = self.record(kind)
            for page in ({"items": [good, good], "next_cursor": None},
                         {"items": [{**good, "id": "bad"}], "next_cursor": None},
                         {"items": [good], "next_cursor": self.target},
                         {"items": [good], "next_cursor": "https://example.test/secret"},
                         {"items": [{**good, "internal": "hidden-internal"}], "next_cursor": None},
                         {"items": [None], "next_cursor": None},
                         {"items": [{**good, "title" if kind == "videos" else "reason": []}], "next_cursor": None},
                         {"items": [], "next_cursor": None, "extra": "hidden-internal"}):
                with patch("web.views._api", side_effect=[(200, self.account), (200, page)]):
                    response = self.client.get(reverse(f"moderation-{kind}"))
                self.assertEqual(response.status_code, 503)
                self.assertNotContains(response, "hidden-internal", status_code=503)
            self.assertFalse(valid_queue_page({"items": [good], "next_cursor": None}, kind, cursor=self.target))

    def test_empty_queues_and_gateway_errors_are_non_enumerating(self):
        self.login()
        for kind in ACTIONS:
            with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [], "next_cursor": None})]):
                self.assertContains(self.client.get(reverse(f"moderation-{kind}")), "No records awaiting review")
        for status in (403, 404, 500, 502, 503):
            with patch("web.views._api", side_effect=[(200, self.account), (status, {
                    "detail": "private-token internal-host person@example.test"})]):
                response = self.client.get(reverse("moderation-videos"))
            self.assertEqual(response.status_code, status if status in (403, 404) else 503)
            for internal in ("private-token", "internal-host", "person@example.test"):
                self.assertNotIn(internal.encode(), response.content)
        with patch("web.views._api", side_effect=[(200, self.account), (401, {"detail": "private-token"})]):
            self.assertRedirects(self.client.get(reverse("moderation-videos")), "/login/?expired=1", fetch_redirect_response=False)
        self.assertFalse(WebCredential.objects.exists())
        self.assertContains(self.client.get("/login/?expired=1"), "Your session has expired")

    def test_cross_resource_detail_and_decision_gateway_denials_preserve_status(self):
        self.login()
        with patch("web.views._api", side_effect=[(200, self.account), (200, self.page("videos"))]):
            self.assertEqual(self.client.get(self.detail_url("videos", str(uuid.uuid4()))).status_code, 404)
        for status in (403, 404):
            intent = self.intent("videos")
            with patch("web.views._api", side_effect=[(200, self.account), (status, {"detail": "private"})]):
                response = self.client.post(self.detail_url("videos"), {
                    "intent": intent, "action": "publish", "reason": "A valid review reason."})
            self.assertEqual(response.status_code, status)
            self.assertNotIn(b"private", response.content)

    def test_content_is_escaped_and_get_never_submits_decision(self):
        self.login()
        record = {**self.record("videos"), "title": '<script>alert("x")</script>'}
        for url in (reverse("moderation-videos"), self.detail_url("videos")):
            with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [record], "next_cursor": None})]) as api:
                response = self.client.get(url)
            self.assertContains(response, "&lt;script&gt;")
            self.assertNotContains(response, "<script>")
            self.assertTrue(all(call.kwargs.get("method", "GET") == "GET" for call in api.call_args_list))

    def test_account_calls_use_own_identity_and_preserve_resource_denials(self):
        self.login()
        with patch("web.views._api", side_effect=[(200, self.account), (200, self.account)]) as api:
            self.assertEqual(self.client.post("/admin/account/profile/", {"display_name": "Updated"}).status_code, 302)
            self.assertEqual(api.call_args.args, ("/me",))
            self.assertEqual(api.call_args.kwargs["method"], "PATCH")
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": []})]):
            self.assertContains(self.client.get("/admin/account/sessions/"), "No active sessions")
        for status in (403, 404):
            with patch("web.views._api", side_effect=[(200, self.account), (status, {"detail": "private"})]) as api:
                response = self.client.post(f"/admin/account/sessions/{self.target}/revoke/")
            self.assertEqual(response.status_code, status)
            self.assertEqual(api.call_args.args, ("/me/sessions/" + self.target,))
            self.assertEqual(api.call_args.kwargs["method"], "DELETE")
        with patch("web.views._api", side_effect=[(200, self.account), (204, {})]) as api:
            response = self.client.post("/admin/account/password/", {
                "current_password": secrets.token_urlsafe(30), "new_password": secrets.token_urlsafe(32)})
            self.assertEqual(api.call_args.args, ("/me/password",))
            self.assertEqual(api.call_args.kwargs["method"], "PATCH")
        self.assertRedirects(response, "/login/", fetch_redirect_response=False)
        self.assertFalse(WebCredential.objects.exists())

    def test_gateway_client_sends_idempotency_header_and_rejects_bad_responses(self):
        from web.views import _api
        with patch("web.views.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status, response.read.return_value = 200, b"{}"
            key = secrets.token_urlsafe(32)
            _api("/moderation/videos/" + self.target + "/decisions", method="POST", data={"action": "publish"},
                 token=self.access, idempotency_key=key)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("Idempotency-key"), key)
            self.assertEqual(request.get_header("Authorization"), "Bearer " + self.access)
            for raw in (b"[]", b"not-json", b"x" * 65537):
                response.read.return_value = raw
                self.assertEqual(_api("/me")[0], 503)
        with patch("web.views.build_opener", side_effect=URLError("internal-host private-token")):
            self.assertEqual(_api("/me"), (503, {"detail": "Service unavailable"}))

    def test_identity_account_switch_invalidates_the_session(self):
        self.login()
        with patch("web.views._api", return_value=(200, {**self.account, "id": str(uuid.uuid4())})):
            self.assertRedirects(self.client.get("/admin/"), "/login/?expired=1", fetch_redirect_response=False)
        self.assertFalse(WebCredential.objects.exists())

    def test_get_logout_during_outage_never_revokes_or_clears(self):
        self.login()
        with patch("web.views._api", return_value=(503, {})) as api:
            self.assertEqual(self.client.get("/admin/logout/").status_code, 503)
            api.assert_called_once()
        self.assertTrue(WebCredential.objects.exists())

    def test_bad_decision_receipts_and_session_records_fail_closed(self):
        self.login()
        for change in ({"video_id": str(uuid.uuid4())}, {"action": "remove"},
                       {"status": "pending"}, {"id": "bad"}):
            intent = self.intent("videos")
            result = {"id": str(uuid.uuid4()), "video_id": self.target, "action": "publish", "status": "applied", **change}
            with patch("web.views._api", side_effect=[(200, self.account), (200, result)]):
                self.assertEqual(self.client.post(self.detail_url("videos"), {
                    "intent": intent, "action": "publish", "reason": "A valid review reason."}).status_code, 503)
        for result in ({"items": [None]}, {"items": [{"id": self.target}]}, {"items": [], "extra": "private"}):
            with patch("web.views._api", side_effect=[(200, self.account), (200, result)]):
                self.assertEqual(self.client.get("/admin/account/sessions/").status_code, 503)
