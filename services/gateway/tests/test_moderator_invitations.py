import json
import secrets
import uuid
from unittest.mock import patch

from django.test import SimpleTestCase

from tests.test_accounts import Response


class ModeratorInvitationGatewayTests(SimpleTestCase):
    path = "/api/v1/admin/moderator-invitations"

    def post(self, path, data, **headers):
        return self.client.post(path, json.dumps(data), content_type="application/json", **headers)

    def test_admin_identity_and_idempotency_are_forwarded_without_client_role(self):
        auth = {"HTTP_AUTHORIZATION": "Bearer current-session", "HTTP_IDEMPOTENCY_KEY": secrets.token_urlsafe(32)}
        payload = {"id": str(uuid.uuid4()), "status": "pending", "expires_at": "2026-11-23T12:00:00Z"}
        with patch("service.accounts.signed_internal_request", return_value=Response(202, json.dumps(payload).encode())) as call:
            self.assertEqual(self.post(self.path, {"email": "reviewer@example.test"}, **auth).status_code, 202)
            body = json.loads(call.call_args.kwargs["payload"])
            self.assertEqual(body["access_token"], "current-session")
            self.assertEqual(body["key"], auth["HTTP_IDEMPOTENCY_KEY"])
            self.assertEqual(body["operation"], "create")
            self.assertEqual(call.call_args.args, ("identity", "/internal/auth/moderator-invitations"))
            call.reset_mock()
            self.assertEqual(self.post(self.path, {"role": "administrator"}, **auth).status_code, 400)
            call.assert_not_called()

    def test_missing_auth_key_filters_and_oversized_body_are_rejected(self):
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.client.get(self.path).status_code, 401)
            self.assertEqual(self.post(self.path, {}, HTTP_AUTHORIZATION="Bearer session").status_code, 400)
            self.assertEqual(self.client.get(self.path + "?actor_id=other", HTTP_AUTHORIZATION="Bearer session").status_code, 400)
            self.assertEqual(self.post("/api/v1/auth/moderator-invitations/setup", {"password": "x" * 5000}).status_code, 400)
            call.assert_not_called()

    def test_upstream_secret_fields_and_malformed_enrollment_are_rejected(self):
        with patch("service.accounts.signed_internal_request") as call:
            for payload in ({"secret": "bad", "expires_at": "2026-11-22T12:00:00Z"},
                            {"secret": "A" * 32, "expires_at": "2026-11-22T12:00:00Z", "password": "never-render"}):
                call.return_value = Response(200, json.dumps(payload).encode())
                response = self.post("/api/v1/auth/moderator-invitations/setup", {})
                self.assertEqual(response.status_code, 503)
                self.assertNotIn(b"never-render", response.content)
            call.return_value = Response(200, b'{"items": [], "next_cursor": null, "secret": "never-render"}')
            self.assertEqual(self.client.get(self.path, HTTP_AUTHORIZATION="Bearer session").status_code, 503)

    def test_revocation_cannot_choose_another_actor_and_preserves_no_store(self):
        target = str(uuid.uuid4())
        with patch("service.accounts.signed_internal_request", return_value=Response(204, b"")) as call:
            response = self.post(self.path + "/" + target + "/revoke", {"reason": "Sent in error"},
                HTTP_AUTHORIZATION="Bearer session", HTTP_IDEMPOTENCY_KEY=secrets.token_urlsafe(32))
        self.assertEqual(response.status_code, 204)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(json.loads(call.call_args.kwargs["payload"])["id"], target)
