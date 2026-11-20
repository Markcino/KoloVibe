import json
import uuid
from urllib.error import HTTPError
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse
from .video_fixtures import metadata


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


class VideoGatewayTests(SimpleTestCase):
    def setUp(self):
        self.enterContext(patch("service.engagement_client.like_counts", return_value=None))
        self.enterContext(patch("service.engagement_client.play_counts", return_value=None))

    def test_stale_cursor_is_a_client_error(self):
        with patch("service.videos.signed_internal_request",
                   side_effect=HTTPError("http://127.0.0.1", 400, "Invalid query", {}, None)):
            self.assertEqual(self.client.get(reverse("videos"),
                {"cursor": str(uuid.uuid4())}).status_code, 400)

    def test_repeated_filters_and_malformed_cursor_are_rejected(self):
        with patch("service.videos.signed_internal_request") as call:
            self.assertEqual(self.client.get(reverse("videos") +
                "?creator_id=" + str(uuid.uuid4()) + "&creator_id=" + str(uuid.uuid4())).status_code, 400)
            call.assert_not_called()
            call.return_value = Response(b'{"items":[],"next_cursor":"bad"}')
            self.assertEqual(self.client.get(reverse("videos")).status_code, 503)

    def test_returns_live_empty_content_response(self):
        with patch("service.videos.signed_internal_request") as call:
            call.return_value = Response(b'{"items":[],"next_cursor":null}')
            response = self.client.get(reverse("videos"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": [], "next_cursor": None})
        self.assertEqual(call.call_args.args, ("content", "/internal/videos"))
        self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {})

    def test_search_forwards_normalized_query_and_rejects_invalid_input(self):
        with patch("service.videos.signed_internal_request") as call:
            url = reverse("api-videos")
            self.assertEqual(self.client.get(url, {"q": "x" * 101}).status_code, 400)
            self.assertEqual(self.client.get(url + "?q=river&q=sea").status_code, 400)
            call.assert_not_called()
            call.return_value = Response(b'{"items":[],"next_cursor":null}')
            self.assertEqual(self.client.get(url, {"q": " River "}).status_code, 200)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {"q": "River"})

    def test_rejects_invalid_filter_without_calling_service(self):
        with patch("service.videos.signed_internal_request") as call:
            self.assertEqual(self.client.get(reverse("videos") + "?creator_id=bad").status_code, 400)
            self.assertEqual(self.client.get(reverse("videos") + "?unexpected=1").status_code, 400)
            call.assert_not_called()

    def test_fails_closed_when_content_unavailable_or_malformed(self):
        with patch("service.videos.signed_internal_request") as call:
            call.side_effect = OSError("unavailable")
            self.assertEqual(self.client.get(reverse("videos")).status_code, 503)
            call.side_effect = None
            call.return_value = Response(b'{"items":"invalid"}')
            self.assertEqual(self.client.get(reverse("videos")).status_code, 503)
            call.return_value = Response(b'{"items":[{"state":"draft"}]}')
            self.assertEqual(self.client.get(reverse("videos")).status_code, 503)

    def test_write_is_not_supported(self):
        self.assertEqual(self.client.post(reverse("videos"), data={}).status_code, 405)

    def test_detail_returns_only_validated_approved_record(self):
        video_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        payload = {"id": str(video_id), "creator_id": str(creator_id),
                   "title": "Original", "description": "", "state": "published",
                   "created_at": "2026-10-31T00:00:00+00:00", **metadata()}
        with patch("service.videos.signed_internal_request") as call:
            call.return_value = Response(json.dumps(payload).encode())
            response = self.client.get(reverse("api-video-detail", args=[video_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload | {"like_count": None, "play_count": None})
        self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {"video_id": str(video_id)})

    def test_detail_rejects_mismatched_record(self):
        video_id = uuid.uuid4()
        with patch("service.videos.signed_internal_request") as call:
            call.return_value = Response(json.dumps({"id": str(uuid.uuid4()),
                "creator_id": str(uuid.uuid4()), "title": "Another", "state": "published"}).encode())
            self.assertEqual(self.client.get(reverse("api-video-detail", args=[video_id])).status_code, 503)
