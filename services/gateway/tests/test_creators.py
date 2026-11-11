import json
import uuid
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit):
        return self.payload[:limit]


class CreatorGatewayTests(SimpleTestCase):
    def test_public_profile_is_validated(self):
        creator_id = uuid.uuid4()
        payload = {"id": str(creator_id), "user_id": str(uuid.uuid4()),
                   "handle": "original-voice", "bio": "", "status": "active"}
        with patch("service.creators.signed_internal_request") as call:
            call.return_value = Response(json.dumps(payload).encode())
            result = self.client.get(reverse("api-creator-detail", args=[creator_id]))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), payload)
        self.assertEqual(call.call_args.args, ("creators", "/internal/creators/profile"))

    def test_restricted_profile_cannot_pass_gateway(self):
        creator_id = uuid.uuid4()
        payload = {"id": str(creator_id), "user_id": str(uuid.uuid4()),
                   "handle": "original-voice", "bio": "", "status": "restricted"}
        with patch("service.creators.signed_internal_request") as call:
            call.return_value = Response(json.dumps(payload).encode())
            result = self.client.get(reverse("api-creator-detail", args=[creator_id]))
        self.assertEqual(result.status_code, 503)

    def test_search_accepts_active_results_and_fails_closed_on_restricted_results(self):
        profile = {"id": str(uuid.uuid4()), "user_id": str(uuid.uuid4()),
                   "handle": "river-voice", "bio": "", "status": "active"}
        with patch("service.creators.signed_internal_request") as call:
            url = reverse("api-creator-search")
            self.assertEqual(self.client.get(url, {"q": ""}).status_code, 400)
            call.assert_not_called()
            page = {"items": [profile], "next_cursor": None}
            call.return_value = Response(json.dumps(page).encode())
            self.assertEqual(self.client.get(url, {"q": " river "}).json(), page)
            self.assertEqual(call.call_args.args, ("creators", "/internal/creators/search"))
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {"q": "river"})
            profile["status"] = "restricted"
            call.return_value = Response(json.dumps(page).encode())
            self.assertEqual(self.client.get(url, {"q": "river"}).status_code, 503)
