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
