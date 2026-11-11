import json
import secrets
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from tests.test_accounts import Response


class PreferencesPrivacyGatewayTests(SimpleTestCase):
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
