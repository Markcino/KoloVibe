import json
import secrets
import uuid
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

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
    def test_reauthentication_requires_bearer_and_only_forwards_current_password(self):
        path = reverse("reauthenticate")
        auth = {"HTTP_AUTHORIZATION": "Bearer current-session"}
        password = secrets.token_urlsafe(32)
        proof = {"reauth_token": secrets.token_urlsafe(48), "expires_at": "2026-11-11T12:05:00+00:00"}
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.post("reauthenticate", {"current_password": password}).status_code, 401)
            for data in ({}, {"current_password": None}, {"current_password": ""},
                         {"current_password": "x" * 129}, {"current_password": password, "account_id": "other"}):
                self.assertEqual(self.post("reauthenticate", data, **auth).status_code, 400)
            call.assert_not_called()
            call.return_value = Response(200, json.dumps(proof).encode())
            response = self.post("reauthenticate", {"current_password": password}, **auth)
            self.assertEqual(response.json(), proof)
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertEqual(call.call_args.args, ("identity", "/internal/auth/reauthenticate"))
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {
                "access_token": "current-session", "current_password": password})
            self.assertEqual(self.client.get(path, **auth).status_code, 405)

    def test_reauthentication_preserves_generic_errors_and_429_and_checks_response(self):
        auth = {"HTTP_AUTHORIZATION": "Bearer current-session"}
        with patch("service.accounts.signed_internal_request") as call:
            for status, detail in ((400, "Reauthentication failed"), (429, "Too many attempts")):
                call.side_effect = HTTPError("https://identity.invalid/internal", status, "", {},
                                             BytesIO(json.dumps({"detail": detail}).encode()))
                response = self.post("reauthenticate", {"current_password": secrets.token_urlsafe(24)}, **auth)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"detail": detail})
            call.side_effect = None
            for data in ({"reauth_token": "short", "expires_at": "2026-11-11T00:00:00Z"},
                         {"reauth_token": "x" * 64, "expires_at": "bad-date"},
                         {"reauth_token": "x" * 64, "expires_at": "2026-11-11T00:00:00"},
                         {"reauth_token": "x" * 64, "expires_at": "2026-11-11T00:00:00Z", "password": secrets.token_urlsafe(24)}):
                call.return_value = Response(200, json.dumps(data).encode())
                self.assertEqual(self.post("reauthenticate", {"current_password": secrets.token_urlsafe(24)}, **auth).status_code, 503)

    def test_protected_requests_revalidate_session_every_time_and_fail_closed(self):
        auth = {"HTTP_AUTHORIZATION": "Bearer same-unexpired-access-token"}
        user = {"id": str(uuid.uuid4()), "email": "viewer@example.test", "display_name": "Viewer",
                "roles": ["viewer"], "created_at": "2026-11-11T12:00:00Z"}
        with patch("service.accounts.signed_internal_request") as call:
            call.side_effect = [Response(200, json.dumps({"user": user, "session_id": "current"}).encode()),
                                HTTPError("https://identity.invalid/internal", 401, "", {},
                                          BytesIO(b'{"detail":"Invalid session"}')),
                                OSError("unavailable")]
            self.assertEqual(self.client.get(reverse("me"), **auth).status_code, 200)
            self.assertEqual(self.client.get(reverse("me"), **auth).status_code, 401)
            self.assertEqual(self.client.get(reverse("me"), **auth).status_code, 503)
            self.assertEqual(call.call_count, 3)
            self.assertTrue(all(args.args == ("identity", "/internal/auth/validate") for args in call.call_args_list))
            self.assertTrue(all(json.loads(args.kwargs["payload"]) == {
                "access_token": "same-unexpired-access-token"} for args in call.call_args_list))

    def test_profile_update_forwards_only_display_name(self):
        account = {"id": "00000000-0000-4000-8000-000000000001",
                   "email": "viewer@example.test", "display_name": "New Name",
                   "created_at": "2026-11-11T00:00:00+00:00", "roles": ["viewer"]}
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.client.patch(reverse("me"),
                data=json.dumps({"display_name": "New Name"}),
                content_type="application/json").status_code, 401)
            call.return_value = Response(200, json.dumps({"user": account}).encode())
            response = self.client.patch(reverse("me"),
                data=json.dumps({"display_name": "New Name"}),
                content_type="application/json", HTTP_AUTHORIZATION="Bearer test-token")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), account)
            self.assertEqual(call.call_args.args, ("identity", "/internal/auth/profile"))
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]),
                             {"access_token": "test-token", "display_name": "New Name"})

    def test_password_routes_forward_only_valid_fields_and_current_bearer(self):
        password = secrets.token_urlsafe(28)
        access = secrets.token_urlsafe(48)
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(204, b"")
            self.assertEqual(self.post("reset-request", {"email": "viewer@example.test"}).status_code, 204)
            self.assertEqual(call.call_args.args, ("identity", "/internal/auth/password/reset-request"))
            self.assertEqual(self.post("reset-password", {
                "code": secrets.token_urlsafe(48), "new_password": password,
            }).status_code, 204)
            self.assertEqual(call.call_args.args, ("identity", "/internal/auth/password/reset"))
            self.assertEqual(self.client.patch(reverse("change-password"),
                data=json.dumps({"current_password": password, "new_password": password}),
                content_type="application/json").status_code, 401)
            self.assertEqual(self.client.patch(reverse("change-password"),
                data=json.dumps({"current_password": password, "new_password": password}),
                content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 204)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {
                "access_token": access, "current_password": password, "new_password": password,
            })
            call.assert_called()

    def post(self, name, data, **headers):
        return self.client.post(reverse(name), data=json.dumps(data),
                                content_type="application/json", **headers)

    def test_login_forwards_only_expected_fields(self):
        entered = secrets.token_urlsafe(24)
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(200, b'{"access_token":"a","refresh_token":"b"}')
            result = self.post("login", {"email": "a@example.test", "password": entered})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(call.call_args.args, ("identity", "/internal/auth/login"))
        self.assertEqual(json.loads(call.call_args.kwargs["payload"]),
                         {"email": "a@example.test", "password": entered})

    def test_resend_forwards_email_without_requiring_a_session(self):
        data = {"email": "viewer@example.test"}
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(204, b"")
            result = self.post("verification-resend", data)
        self.assertEqual(result.status_code, 204)
        self.assertEqual(result.content, b"")
        self.assertEqual(call.call_args.args, ("identity", "/internal/auth/verification/resend"))
        self.assertEqual(json.loads(call.call_args.kwargs["payload"]), data)

    def test_rejects_extra_fields_before_identity_call(self):
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.post("register", {"email": "a", "role": "admin"}).status_code, 400)
            call.assert_not_called()

    def test_session_management_requires_bearer_and_forwards_target(self):
        collection = reverse("account-sessions")
        target = uuid.uuid4()
        detail = reverse("revoke-account-session", args=[target])
        token = secrets.token_urlsafe(24)
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.client.get(collection).status_code, 401)
            self.assertEqual(self.client.delete(detail).status_code, 401)
            call.assert_not_called()
            call.return_value = Response(200, b'{"items":[]}')
            response = self.client.get(collection, HTTP_AUTHORIZATION=f"Bearer {token}")
            self.assertEqual(response.json(), {"items": []})
            self.assertIn("no-store", response.headers["Cache-Control"])
            call.return_value = Response(204, b"")
            self.assertEqual(self.client.delete(detail,
                HTTP_AUTHORIZATION=f"Bearer {token}").status_code, 204)
            self.assertEqual(call.call_args.args, ("identity", "/internal/auth/sessions"))
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]),
                             {"access_token": token, "session_id": str(target)})

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

    def test_privileged_login_challenge_and_mfa_verification_are_forwarded(self):
        challenge = secrets.token_urlsafe(48)
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(202, json.dumps({
                "mfa_required": True, "challenge_token": challenge, "expires_in": 300}).encode())
            response = self.post("login", {"email": "reviewer@example.test", "password": "input"})
            self.assertEqual(response.status_code, 202)
            self.assertNotIn("access_token", response.json())
            call.return_value = Response(200, b'{"access_token":"a","refresh_token":"b"}')
            response = self.post("mfa-verify", {"challenge_token": challenge, "code": "123456"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(call.call_args.args, ("identity", "/internal/auth/mfa/verify"))
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.post("mfa-verify", {"role": "administrator"}).status_code, 400)
            call.assert_not_called()
