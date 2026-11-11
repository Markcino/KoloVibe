import json
from uuid import uuid4
from unittest.mock import patch

from django.http import JsonResponse
from django.test import SimpleTestCase
from django.urls import reverse

from .test_videos import Response


class VideoLikeGatewayTests(SimpleTestCase):
    def setUp(self):
        self.video_id = str(uuid4())
        self.account_id = str(uuid4())
        self.creator_id = str(uuid4())
        self.url = reverse("api-video-like", args=[self.video_id])

    @patch("service.likes.signed_internal_request")
    def test_anonymous_request_never_reaches_engagement(self, engagement):
        self.assertEqual(self.client.put(self.url, data=b"").status_code, 401)
        engagement.assert_not_called()

    @patch("service.likes.signed_internal_request")
    @patch("service.likes.read_public_video")
    @patch("service.likes.current_account")
    def test_like_requires_a_public_video_and_uses_the_verified_account(self, account, video, engagement):
        account.return_value = JsonResponse({"id": self.account_id, "roles": ["viewer"]})
        video.return_value = JsonResponse({"detail": "Not found"}, status=404)
        self.assertEqual(self.client.put(self.url, data=b"").status_code, 404)
        engagement.assert_not_called()

        video.return_value = JsonResponse({"id": self.video_id, "creator_id": self.creator_id})
        expected = {"video_id": self.video_id, "liked": True, "like_count": 1}
        engagement.return_value = Response(json.dumps(expected).encode())
        response = self.client.put(self.url, data=b"")
        self.assertEqual(response.json(), expected)
        self.assertEqual(engagement.call_args.args, ("engagement", "/internal/likes"))
        self.assertEqual(json.loads(engagement.call_args.kwargs["payload"]), {
            "video_id": self.video_id, "liked": True, "account_id": self.account_id, "creator_id": self.creator_id,
        })

        engagement.reset_mock()
        self.assertEqual(self.client.put(
            self.url, data=b'{"account_id":"override"}', content_type="application/json",
        ).status_code, 400)
        engagement.assert_not_called()

    @patch("service.likes.signed_internal_request")
    @patch("service.likes.read_public_video")
    @patch("service.likes.current_account")
    def test_non_engagement_roles_cannot_like_or_unlike(self, account, video, engagement):
        for roles in ([], ["moderator"], ["administrator"], ["admin"], ["support"], ["finance"],
                      ["worker"], ["viewer", "moderator"], ["unrecognized"]):
            with self.subTest(roles=roles):
                account.return_value = JsonResponse({"id": self.account_id, "roles": roles})
                self.assertEqual(self.client.put(self.url, data=b"").status_code, 403)
                self.assertEqual(self.client.delete(self.url, data=b"").status_code, 403)
        video.assert_not_called()
        engagement.assert_not_called()

    @patch("service.likes.signed_internal_request")
    @patch("service.likes.current_account")
    def test_creator_can_remove_a_like(self, account, engagement):
        account.return_value = JsonResponse({"id": self.account_id, "roles": ["creator"]})
        response = Response(json.dumps({"video_id": self.video_id, "liked": False, "like_count": 0}).encode())
        engagement.return_value = response
        self.assertEqual(self.client.delete(self.url, data=b"").status_code, 200)
        self.assertEqual(json.loads(engagement.call_args.kwargs["payload"]), {
            "video_id": self.video_id, "account_id": self.account_id, "liked": False,
        })

    @patch("service.likes.signed_internal_request")
    @patch("service.likes.read_public_video")
    @patch("service.likes.current_account")
    def test_status_reads_only_signed_in_viewers_own_state(self, account, video, engagement):
        account.return_value = JsonResponse({"id": self.account_id, "roles": ["viewer"]})
        video.return_value = JsonResponse({"id": self.video_id, "creator_id": self.creator_id})
        engagement.return_value = Response(json.dumps({
            "video_id": self.video_id, "liked": False, "like_count": 0,
        }).encode())
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["liked"])
        self.assertIn("no-store", result.headers["Cache-Control"])
        self.assertEqual(engagement.call_args.args, ("engagement", "/internal/likes/status"))
        self.assertEqual(json.loads(engagement.call_args.kwargs["payload"]), {
            "account_id": self.account_id, "video_id": self.video_id,
        })
