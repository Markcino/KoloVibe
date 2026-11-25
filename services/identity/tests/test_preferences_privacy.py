import json
import re
import secrets

from django.core import mail
from django.test import RequestFactory, TestCase, override_settings

from service import accounts, legal, preferences_privacy
from service.models import Account, NotificationPreferences, PrivacyRequest, SecurityEvent

ACCEPTED = {kind: legal.DOCUMENTS[kind].version for kind in legal.REQUIRED}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EMAIL_HOST="smtp.example.test",
                   DEFAULT_FROM_EMAIL="noreply@example.test")

class PreferencesPrivacyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.password = secrets.token_urlsafe(24)
        self.first = self._account("first@example.test")
        self.second = self._account("second@example.test")

    def _post(self, view, body):
        if view is accounts.register and "accepted" not in body:
            body = {**body, "accepted": ACCEPTED}  # Decision B: callers accept the current required versions
        return view(self.factory.post("/internal/test", json.dumps(body),
                                      content_type="application/json"))

    def _account(self, email):
        self._post(accounts.register, {"email": email, "password": self.password,
                                       "display_name": "Viewer"})
        code = re.search(r": ([0-9]{6})\n", mail.outbox[-1].body).group(1)
        self._post(accounts.verify_email, {"email": email, "code": code})
        session = self._post(accounts.login, {"email": email, "password": self.password})
        return json.loads(session.content)["access_token"]

    def test_preferences_are_owned_and_fields_are_strict_booleans(self):
        self.assertEqual(json.loads(self._post(preferences_privacy.preferences, {
            "access_token": self.first, "operation": "get"}).content),
            {"email_notifications": False, "push_notifications": False})
        response = self._post(preferences_privacy.preferences, {
            "access_token": self.first, "operation": "patch",
            "email_notifications": True, "push_notifications": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(self._post(preferences_privacy.preferences, {
            "access_token": self.second, "operation": "get"}).content)["email_notifications"], False)
        self.assertEqual(self._post(preferences_privacy.preferences, {
            "access_token": self.first, "operation": "patch",
            "email_notifications": 1, "push_notifications": False}).status_code, 400)
        self.assertEqual(NotificationPreferences.objects.count(), 1)

    def test_privacy_receipt_requires_reauthentication_and_never_deletes(self):
        fields = {"access_token": self.first, "operation": "create",
                  "kind": "deletion", "current_password": self.password}
        self.assertEqual(self._post(preferences_privacy.privacy_requests,
                                    {**fields, "current_password": self.password + "!wrong"}).status_code, 400)
        first = self._post(preferences_privacy.privacy_requests, fields)
        self.assertEqual(first.status_code, 201)
        duplicate = self._post(preferences_privacy.privacy_requests, fields)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(json.loads(duplicate.content)["code"], "request_open")
        self.assertEqual(PrivacyRequest.objects.count(), 1)
        self.assertEqual(PrivacyRequest.objects.get().status, "received")
        self.assertEqual(Account.objects.count(), 2)
        self.assertEqual(json.loads(self._post(preferences_privacy.privacy_requests,
            {"access_token": self.second, "operation": "list"}).content)["items"], [])
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_request_received").count(), 1)

    def test_privacy_request_rejects_unknown_fields_and_expired_session(self):
        self.assertEqual(self._post(preferences_privacy.privacy_requests, {
            "access_token": self.first, "operation": "create", "kind": "deletion",
            "current_password": self.password, "delete_now": True}).status_code, 400)
        self.assertEqual(self._post(accounts.revoke,
            {"access_token": self.first}).status_code, 204)
        self.assertEqual(self._post(preferences_privacy.privacy_requests, {
            "access_token": self.first, "operation": "list"}).status_code, 401)
