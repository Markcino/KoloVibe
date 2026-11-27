import json
import secrets
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from django.test import SimpleTestCase
from django.urls import reverse

from tests.test_accounts import Response


class PreferencesPrivacyGatewayTests(SimpleTestCase):
    def test_token_proof_is_forwarded_and_open_request_code_is_preserved(self):
        path = reverse("account-privacy-requests")
        proof = secrets.token_urlsafe(48)
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(201, b'{"id":"00000000-0000-4000-8000-000000000001","kind":"deletion","status":"received","created_at":"2026-11-11T00:00:00Z"}')
            response = self.client.post(path, data=json.dumps({"kind": "deletion", "reauth_token": proof}),
                                        content_type="application/json", **self.auth)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {
                "access_token": self.token, "operation": "create", "kind": "deletion", "reauth_token": proof})
            call.side_effect = HTTPError("https://identity.invalid/internal", 409, "", {},
                BytesIO(b'{"detail":"An open request already exists","code":"request_open","internal":"redacted"}'))
            response = self.client.post(path, data=json.dumps({"kind": "deletion", "reauth_token": proof}),
                                        content_type="application/json", **self.auth)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json(), {"detail": "An open request already exists", "code": "request_open"})

    def test_all_receipt_statuses_are_accepted_and_unknown_status_is_rejected(self):
        path = reverse("account-privacy-requests")
        receipt = {"id": "00000000-0000-4000-8000-000000000001", "kind": "access",
                   "created_at": "2026-11-11T00:00:00Z"}
        with patch("service.accounts.signed_internal_request") as call:
            items = [{**receipt, "status": status} for status in ("received", "in_review", "completed", "declined")]
            call.return_value = Response(200, json.dumps({"items": items}).encode())
            self.assertEqual(self.client.get(path, **self.auth).json(), {"items": items})
            call.return_value = Response(200, json.dumps({"items": [{**receipt, "status": "unknown"}]}).encode())
            self.assertEqual(self.client.get(path, **self.auth).status_code, 503)

    def setUp(self):
        self.token = secrets.token_urlsafe(24)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_preference_routes_require_owner_and_strict_fields(self):
        path = reverse("account-preferences")
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.patch(path, data=json.dumps({
                "email_notifications": 1, "push_notifications": False}),
                content_type="application/json", **self.auth).status_code, 400)
            call.assert_not_called()
            call.return_value = Response(200, b'{"email_notifications":false,"push_notifications":false}')
            self.assertEqual(self.client.get(path, **self.auth).status_code, 200)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]),
                             {"access_token": self.token, "operation": "get"})
            self.assertEqual(self.client.patch(path, data=json.dumps({
                "email_notifications": True, "push_notifications": False}),
                content_type="application/json", **self.auth).status_code, 200)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {
                "access_token": self.token, "operation": "patch",
                "email_notifications": True, "push_notifications": False})
            call.return_value = Response(200, b'{"email_notifications":true,"push_notifications":false,"session":"leak"}')
            self.assertEqual(self.client.get(path, **self.auth).status_code, 503)

    def test_privacy_request_requires_reauthentication_field_and_forwards_no_extra(self):
        path = reverse("account-privacy-requests")
        password = secrets.token_urlsafe(24)
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.client.post(path, data=json.dumps({
                "kind": "deletion", "current_password": password}),
                content_type="application/json").status_code, 401)
            self.assertEqual(self.client.post(path, data=json.dumps({
                "kind": "deletion", "current_password": password, "delete_now": True}),
                content_type="application/json", **self.auth).status_code, 400)
            call.assert_not_called()
            call.return_value = Response(201, b'{"id":"00000000-0000-4000-8000-000000000001","kind":"deletion","status":"received","created_at":"2026-11-11T00:00:00+00:00"}')
            response = self.client.post(path, data=json.dumps({
                "kind": "deletion", "current_password": password}),
                content_type="application/json", **self.auth)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["status"], "received")
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {
                "access_token": self.token, "operation": "create",
                "kind": "deletion", "current_password": password})
            call.return_value = Response(200, b'{"items":[]}')
            self.assertEqual(self.client.get(path, **self.auth).json(), {"items": []})


class PrivacyExportGatewayTests(SimpleTestCase):
    """Mandate 3.3: the app retrieves its own access export through the gateway; Identity decides access."""

    def setUp(self):
        self.token = secrets.token_urlsafe(24)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.target = "00000000-0000-4000-8000-000000000001"
        self.path = reverse("account-privacy-export", kwargs={"target_id": self.target})
        self.export = {"request_id": self.target, "generated_at": "2026-11-27T10:00:00+00:00",
                       "expires_at": "2026-11-28T10:00:00+00:00",
                       "services": {"identity": {"data": {"account": [{"email": "person@example.test"}]},
                                                 "withheld": [], "truncated": []},
                                    "engagement": {"data": {"likes": [{"video_id": "v", "created_at": None}]},
                                                   "withheld": ["fraud_holds"], "truncated": []}}}

    def post(self, body, **extra):
        return self.client.post(self.path, data=json.dumps(body), content_type="application/json", **extra)

    def test_the_export_is_forwarded_with_a_fresh_proof_and_never_cached(self):
        password = secrets.token_urlsafe(24)
        with patch("service.accounts.signed_internal_request") as call:
            call.return_value = Response(200, json.dumps(self.export).encode())
            response = self.post({"current_password": password}, **self.auth)
        self.assertEqual((response.status_code, response.json()), (200, self.export))
        self.assertIn("no-cache", response.headers["Cache-Control"])
        self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {
            "access_token": self.token, "operation": "export", "id": self.target, "current_password": password})

    def test_missing_token_or_proof_never_reaches_identity(self):
        with patch("service.accounts.signed_internal_request") as call:
            self.assertEqual(self.post({"current_password": "x"}).status_code, 401)
            for body in ({}, {"current_password": ""}, {"reauth_token": "short"},
                         {"current_password": "x", "kind": "access"}):
                self.assertEqual(self.post(body, **self.auth).status_code, 400, body)
            self.assertEqual(self.client.get(self.path, **self.auth).status_code, 405)
        call.assert_not_called()

    def test_identity_denials_pass_through_with_their_code(self):
        for status, code in ((404, None), (409, "export_not_ready"), (410, "export_expired")):
            body = {"detail": "Refused", "internal": "redacted"} | ({"code": code} if code else {})
            with self.subTest(status=status), patch("service.accounts.signed_internal_request") as call:
                call.side_effect = HTTPError("https://identity.invalid", status, "", {},
                                             BytesIO(json.dumps(body).encode()))
                response = self.post({"current_password": "x"}, **self.auth)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"detail": "Refused"} | ({"code": code} if code else {}))

    def test_a_malformed_export_is_not_passed_on(self):
        for wrong in ({"extra": 1}, {"request_id": "nope"},
                      {"services": {"engagement": self.export["services"]["engagement"]}},
                      {"services": {**self.export["services"], "finance": {"data": {}, "withheld": [],
                                                                            "truncated": []}}},
                      {"services": {"identity": {"data": {"account": [{"nested": {"a": 1}}]},
                                                 "withheld": [], "truncated": []}}},
                      {"services": {"identity": {"data": {"Bad Name": []}, "withheld": [], "truncated": []}}}):
            with self.subTest(wrong=wrong), patch("service.accounts.signed_internal_request") as call:
                call.return_value = Response(200, json.dumps(self.export | wrong).encode())
                self.assertEqual(self.post({"current_password": "x"}, **self.auth).status_code, 503)
