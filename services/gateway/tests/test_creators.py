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
    def setUp(self):
        self.enterContext(patch("service.engagement_client.follower_count", return_value=None))

    def test_public_profile_is_validated(self):
        creator_id = uuid.uuid4()
        payload = {"id": str(creator_id), "user_id": str(uuid.uuid4()),
                   "handle": "original-voice", "bio": "", "status": "active", "display_name": "Voice", "location": ""}
        with patch("service.creators.signed_internal_request") as call, \
                patch("service.content_client.published_video_count", return_value=0):
            call.return_value = Response(json.dumps(payload).encode())
            result = self.client.get(reverse("api-creator-detail", args=[creator_id]))
        self.assertEqual(result.status_code, 200)
        public = {key: value for key, value in payload.items() if key != "user_id"}
        self.assertEqual(result.json(), public | {"published_video_count": 0, "follower_count": None})
        self.assertNotIn("user_id", result.json())
        self.assertNotIn(payload["user_id"], result.content.decode())
        self.assertEqual(call.call_args.args, ("creators", "/internal/creators/profile"))

    def test_public_profile_without_account_id_from_upstream_is_refused(self):
        creator_id = uuid.uuid4()
        payload = {"id": str(creator_id), "handle": "original-voice", "bio": "",
                   "status": "active", "display_name": "Voice", "location": ""}
        with patch("service.creators.signed_internal_request") as call, \
                patch("service.content_client.published_video_count", return_value=0):
            call.return_value = Response(json.dumps(payload).encode())
            result = self.client.get(reverse("api-creator-detail", args=[creator_id]))
        self.assertEqual(result.status_code, 503)

    def test_internal_read_keeps_account_id_for_authorization_only(self):
        from service.creators import read_creator
        creator_id = uuid.uuid4()
        account = str(uuid.uuid4())
        payload = {"id": str(creator_id), "user_id": account, "handle": "original-voice", "bio": "",
                   "status": "active", "display_name": "Voice", "location": ""}
        with patch("service.creators.signed_internal_request") as call:
            call.return_value = Response(json.dumps(payload).encode())
            self.assertEqual(json.loads(read_creator(creator_id).content)["user_id"], account)

    def test_restricted_profile_cannot_pass_gateway(self):
        creator_id = uuid.uuid4()
        payload = {"id": str(creator_id), "user_id": str(uuid.uuid4()),
                   "handle": "original-voice", "bio": "", "status": "restricted"}
        with patch("service.creators.signed_internal_request") as call:
            call.return_value = Response(json.dumps(payload).encode())
            result = self.client.get(reverse("api-creator-detail", args=[creator_id]))
        self.assertEqual(result.status_code, 503)

    def test_search_accepts_active_results_and_fails_closed_on_restricted_results(self):
        profile = {"id": str(uuid.uuid4()),
                   "handle": "river-voice", "bio": "", "status": "active", "display_name": "River", "location": ""}
        with patch("service.creators.signed_internal_request") as call:
            url = reverse("api-creator-search")
            self.assertEqual(self.client.get(url, {"q": ""}).status_code, 400)
            call.assert_not_called()
            page = {"items": [profile], "next_cursor": None}
            call.return_value = Response(json.dumps(page).encode())
            result = self.client.get(url, {"q": " river "})
            self.assertEqual(result.json(), page)
            self.assertNotIn("user_id", result.content.decode())
            self.assertEqual(call.call_args.args, ("creators", "/internal/creators/search"))
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {"q": "river"})
            profile["status"] = "restricted"
            call.return_value = Response(json.dumps(page).encode())
            self.assertEqual(self.client.get(url, {"q": "river"}).status_code, 503)
            # An upstream that leaks the internal account id is refused, never forwarded.
            profile["status"] = "active"
            profile["user_id"] = str(uuid.uuid4())
            call.return_value = Response(json.dumps(page).encode())
            self.assertEqual(self.client.get(url, {"q": "river"}).status_code, 503)
