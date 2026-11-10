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
        self.url = reverse("api-video-like", args=[self.video_id])

    @patch("service.likes.signed_internal_request")
    def test_anonymous_request_never_reaches_engagement(self, engagement):
        self.assertEqual(self.client.put(self.url, data=b"").status_code, 401)
        engagement.assert_not_called()

    @patch("service.likes.signed_internal_request")
    @patch("service.likes.read_public_video")
    @patch("service.likes.current_account")
    def test_like_requires_a_public_video_and_uses_the_verified_account(self, account, video, engagement):
        account.return_value = JsonResponse({"id": self.account_id})
        video.return_value = JsonResponse({"detail": "Not found"}, status=404)
        self.assertEqual(self.client.put(self.url, data=b"").status_code, 404)
        engagement.assert_not_called()

        video.return_value = JsonResponse({"id": self.video_id})
        expected = {"video_id": self.video_id, "liked": True}
        engagement.return_value = Response(json.dumps(expected).encode())
        response = self.client.put(self.url, data=b"")
        self.assertEqual(response.json(), expected)
        self.assertEqual(engagement.call_args.args, ("engagement", "/internal/likes"))
        self.assertEqual(json.loads(engagement.call_args.kwargs["payload"]), {
            **expected, "account_id": self.account_id,
        })

        engagement.reset_mock()
        self.assertEqual(self.client.put(
            self.url, data=b'{"account_id":"override"}', content_type="application/json",
        ).status_code, 400)
        engagement.assert_not_called()
