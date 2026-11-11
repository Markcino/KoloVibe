import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import SimpleTestCase
from django.urls import reverse


class Response:
    def __init__(self, status, body=b""):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit):
        return self.body[:limit]


class CreatorFollowGatewayTests(SimpleTestCase):
    def setUp(self):
        self.creator_id = uuid4()
        self.account_id = uuid4()
        self.url = reverse("api-creator-follow", args=[self.creator_id])
        self.viewer = JsonResponse({"id": str(self.account_id), "roles": ["viewer"]})
        self.creator = JsonResponse({"id": str(self.creator_id), "user_id": str(uuid4()),
                                     "status": "active", "handle": "creator", "bio": ""})

    def test_requires_login_and_reviewed_creator_for_follow(self):
        self.assertEqual(self.client.put(self.url).status_code, 401)
        with patch("service.follows.current_account", return_value=self.viewer), \
             patch("service.follows.read_creator", return_value=JsonResponse({"detail": "Not found"}, status=404)), \
             patch("service.follows.signed_internal_request") as peer:
            self.assertEqual(self.client.put(self.url).status_code, 404)
            peer.assert_not_called()
        self.creator = JsonResponse({"id": str(self.creator_id),
                                     "user_id": str(self.account_id)})
        with patch("service.follows.current_account", return_value=self.viewer), \
             patch("service.follows.read_creator", return_value=self.creator), \
             patch("service.follows.signed_internal_request") as peer:
            self.assertEqual(self.client.put(self.url).status_code, 403)
            peer.assert_not_called()

    def test_idempotent_intent_is_bound_to_viewer(self):
        with patch("service.follows.current_account", return_value=self.viewer), \
             patch("service.follows.read_creator", return_value=self.creator), \
             patch("service.follows.signed_internal_request") as peer:
            peer.return_value = Response(200, json.dumps({
                "creator_id": str(self.creator_id), "following": True, "follower_count": 1,
            }).encode())
            self.assertEqual(self.client.put(self.url).status_code, 200)
            self.assertEqual(json.loads(peer.call_args.kwargs["payload"]), {
                "account_id": str(self.account_id), "creator_id": str(self.creator_id),
                "operation": "follow",
            })
            peer.return_value = Response(200, json.dumps({"creator_id": str(self.creator_id), "following": False, "follower_count": 0}).encode())
            self.assertEqual(self.client.delete(self.url).status_code, 200)
            self.assertEqual(json.loads(peer.call_args.kwargs["payload"])["operation"], "unfollow")
