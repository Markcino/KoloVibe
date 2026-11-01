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
