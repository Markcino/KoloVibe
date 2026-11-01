import json
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class Response:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit):
        return self.payload[:limit]


class AccountGatewayTests(SimpleTestCase):
    def post(self, name, data, **headers):
        return self.client.post(reverse(name), data=json.dumps(data),
                                content_type="application/json", **headers)

    def test_login_forwards_only_expected_fields(self):
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(200, b'{"access_token":"a","refresh_token":"b"}')
            result = self.post("login", {"email": "a@example.test", "password": "secret"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(call.call_args.args, ("identity", "/internal/auth/login"))
        self.assertEqual(json.loads(call.call_args.kwargs["payload"]),
                         {"email": "a@example.test", "password": "secret"})

    def test_rejects_extra_fields_before_identity_call(self):
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.post("register", {"email": "a", "role": "admin"}).status_code, 400)
            call.assert_not_called()

    def test_me_needs_bearer_and_strips_session_data(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(200, b'{"user":{"id":"1","email":"a@example.test","display_name":"A","roles":["viewer"],"created_at":"2026-10-31T00:00:00+00:00"},"session_id":"secret"}')
            result = self.client.get(reverse("me"), HTTP_AUTHORIZATION="Bearer token")
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("session_id", result.json())
        self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {"access_token": "token"})

    def test_logout_needs_bearer(self):
        self.assertEqual(self.post("logout", {}).status_code, 401)
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(204, b"")
            self.assertEqual(self.post("logout", {}, HTTP_AUTHORIZATION="Bearer token").status_code, 204)

    def test_identity_failure_is_not_exposed(self):
        with patch("service.accounts.signed_internal_request") as call:
            call.side_effect = OSError("private server address")
            response = self.post("login", {"email": "a", "password": "b"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private server address", response.content.decode())
