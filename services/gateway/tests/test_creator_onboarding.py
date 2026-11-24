import json
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from .test_videos import Response


class CreatorOnboardingGatewayTests(SimpleTestCase):
    @patch("service.creator_onboarding.signed_internal_request")
    def test_anonymous_application_never_reaches_creators(self, service):
        response = self.client.get(reverse("creator-application"))
        self.assertEqual(response.status_code, 401)
        service.assert_not_called()

    @patch("service.creator_onboarding.signed_internal_request")
    @patch("service.accounts.signed_internal_request")
    def test_own_application_requires_verified_email_and_binds_actor(self, identity, creators):
        account = str(uuid4())
        payload = {"user": {"id": account, "email": "viewer@example.test", "display_name": "Viewer",
                            "created_at": "2026-11-10T00:00:00Z", "roles": ["viewer"]}}
        endpoint = reverse("creator-application")
        headers = {"HTTP_AUTHORIZATION": "Bearer " + uuid4().hex}

        identity.return_value = Response(json.dumps(payload | {"email_verified": False}).encode())
        self.assertEqual(self.client.get(endpoint, **headers).status_code, 403)
        creators.assert_not_called()
        self.assertIs(json.loads(identity.call_args.kwargs["payload"])["include_email_verification"], True)

        identity.return_value = Response(json.dumps(payload | {"email_verified": True}).encode())
        expected = {"account_id": account, "status": "invited", "creator_id": None}
        creators.return_value = Response(json.dumps(expected).encode())
        response = self.client.get(endpoint, **headers)
        self.assertEqual(response.json(), expected)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(json.loads(creators.call_args.kwargs["payload"]),
                         {"actor_id": account, "role": "viewer", "data": {}})
        self.assertEqual(self.client.get(endpoint + "?account_id=" + str(uuid4()), **headers).status_code, 400)

    @override_settings(KOLOVIBE_SERVICE_NAME="gateway", STAGING_ACCOUNTS=True, STAGING_PRIVILEGED=True)
    def test_staging_path_is_closed_until_the_new_capability_is_enabled(self):
        services = Path(__file__).resolve().parents[2]
        with patch.object(sys, "path", [str(services), *sys.path]):
            from staging_runtime.middleware import RestrictedStagingMiddleware

        check = RestrictedStagingMiddleware(lambda request: JsonResponse({}))
        factory = RequestFactory()
        with self.settings(STAGING_CREATOR_ONBOARDING=False):
            self.assertEqual(check(factory.get("/api/v1/creators/me/application", secure=True)).status_code, 403)
        with self.settings(STAGING_CREATOR_ONBOARDING=True):
            self.assertEqual(check(factory.get("/api/v1/creators/me/application", secure=True)).status_code, 200)
        target = "/api/v1/creator-invitations/" + str(uuid4()) + "/revoke"
        with self.settings(STAGING_CREATOR_ONBOARDING=False):
            self.assertEqual(check(factory.post(target, secure=True)).status_code, 403)
        with self.settings(STAGING_CREATOR_ONBOARDING=True):
            self.assertEqual(check(factory.post(target, secure=True)).status_code, 200)
            self.assertEqual(check(factory.post(target + "/x", secure=True)).status_code, 403)


class CreatorInvitationManagementGatewayTests(SimpleTestCase):
    """Listing and revoking outstanding invitations: the actor and role come from Identity, never the request."""

    def setUp(self):
        self.admin = str(uuid4())
        self.target = str(uuid4())
        self.headers = {"HTTP_AUTHORIZATION": "Bearer " + uuid4().hex}

    def identity(self, mock, role="administrator"):
        user = {"id": self.admin, "email": "a@example.test", "display_name": "Admin",
                "created_at": "2026-11-10T00:00:00Z", "roles": [role]}
        mock.return_value = Response(json.dumps({"user": user}).encode())

    def row(self, **changes):
        return {"account_id": self.target, "status": "invited", "creator_id": None,
                "invited_at": "2026-11-24T10:00:00+00:00", **changes}

    @patch("service.creator_onboarding.signed_internal_request")
    @patch("service.accounts.signed_internal_request")
    def test_outstanding_listing_binds_actor_and_role_and_validates_the_page(self, identity, creators):
        self.identity(identity)
        page = {"items": [self.row()], "next_cursor": None}
        creators.return_value = Response(json.dumps(page).encode())
        response = self.client.get(reverse("creator-invite") + "?cursor=" + str(uuid4()), **self.headers)
        self.assertEqual(response.json(), page)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(creators.call_args.args[:2], ("creators", "/internal/creators/onboarding/outstanding"))
        sent = json.loads(creators.call_args.kwargs["payload"])
        self.assertEqual((sent["actor_id"], sent["role"]), (self.admin, "administrator"))
        for bad in ({"items": [self.row(status="pending")], "next_cursor": None},
                    {"items": [self.row(creator_id=str(uuid4()))], "next_cursor": None},
                    {"items": [self.row(email="x@example.test")], "next_cursor": None},
                    {"items": [self.row(invited_at="2026-11-24T10:00:00")], "next_cursor": None},
                    {"items": [self.row()], "next_cursor": str(uuid4())}):
            creators.return_value = Response(json.dumps(bad).encode())
            self.assertEqual(self.client.get(reverse("creator-invite"), **self.headers).status_code, 503, bad)

    @patch("service.creator_onboarding.signed_internal_request")
    def test_anonymous_listing_and_revocation_never_reach_creators(self, creators):
        self.assertEqual(self.client.get(reverse("creator-invite")).status_code, 401)
        self.assertEqual(self.client.post(reverse("creator-invitation-revoke", args=[self.target]),
                                          "{}", content_type="application/json").status_code, 401)
        creators.assert_not_called()

    @patch("service.creator_onboarding.signed_internal_request")
    @patch("service.accounts.signed_internal_request")
    def test_revocation_takes_its_target_from_the_path_only(self, identity, creators):
        self.identity(identity)
        revoked = {"account_id": self.target, "status": "revoked", "creator_id": None}
        creators.return_value = Response(json.dumps(revoked).encode())
        url = reverse("creator-invitation-revoke", args=[self.target])
        response = self.client.post(url, "{}", content_type="application/json", **self.headers)
        self.assertEqual(response.json(), revoked)
        sent = json.loads(creators.call_args.kwargs["payload"])
        self.assertEqual(sent["data"], {"account_id": self.target})
        self.assertEqual(sent["actor_id"], self.admin)
        creators.reset_mock()
        for body in ('{"account_id": "%s"}' % uuid4(), "[]", "x"):
            self.assertEqual(self.client.post(url, body, content_type="application/json", **self.headers).status_code, 400)
        self.assertEqual(self.client.get(url, **self.headers).status_code, 405)
        creators.assert_not_called()
        creators.return_value = Response(json.dumps(revoked | {"account_id": str(uuid4())}).encode())
        self.assertEqual(self.client.post(url, "{}", content_type="application/json", **self.headers).status_code, 503)

    @patch("service.creator_onboarding.signed_internal_request")
    @patch("service.accounts.signed_internal_request")
    def test_creators_refusals_are_relayed(self, identity, creators):
        from urllib.error import HTTPError
        self.identity(identity)
        url = reverse("creator-invitation-revoke", args=[self.target])
        for code, detail in ((403, "Forbidden"), (404, "Creator invitation not found"),
                             (409, "Only an outstanding invitation can be revoked")):
            creators.side_effect = HTTPError("u", code, "", {}, __import__("io").BytesIO(json.dumps({"detail": detail}).encode()))
            response = self.client.post(url, "{}", content_type="application/json", **self.headers)
            self.assertEqual((response.status_code, response.json()["detail"]), (code, detail))

    @patch("service.creator_onboarding.signed_internal_request")
    @patch("service.accounts.signed_internal_request")
    def test_only_an_administrator_reaches_listing_and_revocation(self, identity, creators):
        for role in ("viewer", "creator", "moderator"):
            self.identity(identity, role=role)
            self.assertEqual(self.client.get(reverse("creator-invite"), **self.headers).status_code, 403, role)
            url = reverse("creator-invitation-revoke", args=[self.target])
            self.assertEqual(self.client.post(url, "{}", content_type="application/json", **self.headers).status_code, 403, role)
        creators.assert_not_called()
