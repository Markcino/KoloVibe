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

    def detail(self, kind):
        return {"record": self.record(kind), "video": {"id": self.target, "title": "Review this video",
                "description": "Video description", "state": "review", "duration_seconds": 30, "rights_status": "flagged"},
                "preview": None, "reports": [], "decisions": [], "history_truncated": {"reports": False, "decisions": False}}

    def detail_url(self, kind, target=None):
        return reverse(f"moderation-{kind}-detail", args=[target or self.target])

    def intent(self, kind, client=None):
        # An administrator's page also asks for assignments; "unavailable" keeps these tests about decisions.
        with patch("web.views._api", side_effect=[(200, self.account), (200, self.detail(kind)), (503, {})]):
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
        self.assertRedirects(self.client.get("/"), "/login/", fetch_redirect_response=False)

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
                with patch("web.views._api", side_effect=[(200, self.account)] + ([(200, {"videos": dict.fromkeys(["review", "published", "rejected", "removed"], 0), "reports": dict.fromkeys(["open", "resolved", "dismissed"], 0), "appeals": dict.fromkeys(["open", "denied", "restored"], 0)}), (200, {"total": 0, "items": [], "next_cursor": None}), (200, {"items": [], "next_cursor": None})] if path == "/admin/" else [(200, {"items": [], "next_cursor": None})] if path == "/admin/audit/" else [])):
                    self.assertEqual(self.client.get(path).status_code, 200)
            for kind in ACTIONS:
                with patch("web.views._api", side_effect=[(200, self.account), (200, self.page(kind))]):
                    response = self.client.get(reverse(f"moderation-{kind}"))
                self.assertEqual(response.status_code, 200)
            with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [], "next_cursor": None, "as_of": "2026-11-21T10:00:00Z"}) if role == "administrator" else (403, {})]):
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
            for query in ("?cursor=bad", "?cursor=x&cursor=y", "?status=unsupported", "?actor_id=" + self.target,
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
                self.assertContains(self.client.get(reverse(f"moderation-{kind}")), "No records match this status")
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
        with patch("web.views._api", side_effect=[(200, self.account), (404, {})]):
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
            with patch("web.views._api", side_effect=[(200, self.account), (200, ({"items": [record], "next_cursor": None} if url == reverse("moderation-videos") else
                    {**self.detail("videos"), "record": record, "video": {**self.detail("videos")["video"], "title": record["title"]}})),
                    (503, {})]) as api:
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


    def test_reviewer_metadata_and_history_are_escaped_and_storage_url_rejected(self):
        self.login("moderator")
        detail = self.detail("videos")
        detail["video"]["description"] = "<script>private</script>"
        with patch("web.views._api", side_effect=[(200, self.account), (200, detail)]) as api:
            response = self.client.get(self.detail_url("videos"))
        self.assertContains(response, "&lt;script&gt;private&lt;/script&gt;")
        self.assertEqual(api.call_args.args, (f"/moderation/videos/{self.target}",))
        detail["preview"] = {"id": self.target, "url": "https://storage.example/secret-key", "expires_at": "2026-11-21T10:00:00Z"}
        with patch("web.views._api", side_effect=[(200, self.account), (200, detail)]):
            self.assertEqual(self.client.get(self.detail_url("videos")).status_code, 503)

    def test_preview_uses_server_credentials_and_is_not_cached(self):
        self.login()
        url = reverse("reviewer-preview", args=[self.target])
        with patch("web.views._api", side_effect=[(200, self.account), (200, b"mp4")]) as api:
            response = self.client.get(url)
        self.assertEqual(response.content, b"mp4")
        self.assertEqual(api.call_args.kwargs, {"token": self.access, "binary": True})
        self.assertIn("no-store", response["Cache-Control"])
        with patch("web.views._api", side_effect=[(200, self.account), (403, {})]):
            self.assertEqual(self.client.get(url).status_code, 403)


    def test_dashboard_displays_only_validated_service_counts(self):
        self.login("moderator")
        totals = {"videos": dict.fromkeys(["review", "published", "rejected", "removed"], 0),
                  "reports": {"open": 7, "resolved": 3, "dismissed": 2}, "appeals": {"open": 2, "denied": 1, "restored": 0}}
        with patch("web.views._api", side_effect=[(200, self.account), (200, totals),
                (200, {"total": 9, "items": [], "next_cursor": None}), (403, {})]):
            response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["totals"]["reports"]["open"], 7)
        self.assertEqual(response.context["holds"]["total"], 9)
        with patch("web.views._api", side_effect=[(200, self.account), (403, {})]):
            self.assertEqual(self.client.get("/admin/").status_code, 403)
        with patch("web.views._api", side_effect=[(200, self.account), (200, {**totals, "videos": {"review": True}})]):
            self.assertEqual(self.client.get("/admin/").status_code, 503)


    def test_unassigned_moderator_sees_empty_state_not_an_error(self):
        self.login("moderator")
        denied = (403, {"detail": "Resource unavailable"})
        with patch("web.views._api", side_effect=[(200, self.account), denied, (403, {})]) as api:
            response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No review assignments yet")
        self.assertTrue(response.context["unassigned"])
        self.assertNotContains(response, "Review workspace")
        # Scoped reads are not attempted: only /me, totals and audit are called.
        self.assertEqual([call.args[0] for call in api.call_args_list],
                         ["/me", "/moderation/totals", "/admin/audit"])
        self.assertTrue(self.client.session.get("authenticated"))
        # Any other 403, and any non-moderator, stays an error and is not downgraded.
        with patch("web.views._api", side_effect=[(200, self.account), (403, {"detail": "Reviewer role required"})]):
            self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.login("administrator")
        with patch("web.views._api", side_effect=[(200, self.account), denied]):
            self.assertEqual(self.client.get("/admin/").status_code, 403)

    def test_audit_filters_pagination_and_malformed_records(self):
        self.login("moderator")
        records = [{"id": str(uuid.uuid4()), "kind": "moderation.reviewer_read", "producer": "moderation",
                    "subject_type": "video", "occurred_at": f"2026-11-21T10:{minute:02d}:00Z"} for minute in reversed(range(20))]
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": records, "next_cursor": records[-1]["id"]})]) as api:
            response = self.client.get("/admin/audit/?producer=moderation")
        self.assertContains(response, "Next page")
        self.assertIn("producer=moderation", response.context["next_query"])
        self.assertEqual(api.call_args.args, ("/admin/audit?producer=moderation",))
        records[0]["actor_id"] = str(uuid.uuid4())
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": records, "next_cursor": None})]):
            self.assertEqual(self.client.get("/admin/audit/").status_code, 503)
        with patch("web.views._api", return_value=(200, self.account)) as api:
            self.assertEqual(self.client.get("/admin/audit/?actor_id=someone").status_code, 400)
            api.assert_called_once()


    def test_audit_datetime_local_filters_are_sent_as_utc_and_redisplayed(self):
        self.login("moderator")
        record = {"id": str(uuid.uuid4()), "kind": "mfa.failed", "producer": "identity",
                  "subject_type": None, "occurred_at": "2026-11-21T10:05:09.123456+00:00"}
        with patch("web.views._api", side_effect=[(200, self.account), (200, {"items": [record], "next_cursor": None})]) as api:
            response = self.client.get("/admin/audit/?since=2026-11-21T09:30&until=2026-11-21T11:00:00%2B01:00")
        self.assertEqual(api.call_args.args, ("/admin/audit?since=2026-11-21T09%3A30%3A00Z&until=2026-11-21T10%3A00%3A00Z",))
        self.assertContains(response, 'type="datetime-local" name="since" value="2026-11-21T09:30"')
        self.assertContains(response, "2026-11-21 · 10:05:09 UTC")
        self.assertContains(response, "Mfa / failed")

    def test_audit_filter_with_invalid_bound_is_forwarded_for_gateway_rejection(self):
        self.login("moderator")
        with patch("web.views._api", side_effect=[(200, self.account), (400, {})]) as api:
            self.client.get("/admin/audit/?since=not-a-date")
        self.assertEqual(api.call_args.args, ("/admin/audit?since=not-a-date",))


    def test_points_review_renders_ledger_and_follows_service_authorization(self):
        self.login("moderator")
        with patch("web.views._api", side_effect=[(200, self.account), (403, {})]) as api:
            self.assertEqual(self.client.get("/admin/points/").status_code, 403)
        self.assertEqual(api.call_args.args, ("/admin/points/balances",))
        self.login()
        page = {"account_id": self.target, "balance": 7, "currency": "POINTS", "as_of": "2026-11-21T10:00:00Z",
                "items": [{"id": str(uuid.uuid4()), "amount": 7, "kind": "award", "rule_version": "v1",
                    "reason_code": "<script>unsafe</script>", "created_at": "2026-11-21T10:00:00Z", "reversal_review_state": "not_reversed"}], "next_cursor": None}
        with patch("web.views._api", side_effect=[(200, self.account), (200, page)]):
            response = self.client.get("/admin/points/", {"account": self.target})
        self.assertContains(response, "Balance 7 POINTS")
        self.assertContains(response, "&lt;script&gt;unsafe&lt;/script&gt;")
        self.assertNotContains(response, 'method="post" action="/admin/points')
        with patch("web.views._api", side_effect=[(200, self.account), (200, {**page, "account_id": str(uuid.uuid4())})]):
            self.assertEqual(self.client.get("/admin/points/", {"account": self.target}).status_code, 503)
