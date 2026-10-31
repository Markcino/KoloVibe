import json
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


class VideoGatewayTests(SimpleTestCase):
    def test_returns_live_empty_content_response(self):
        with patch("service.videos.signed_internal_request") as call:
            call.return_value = Response(b'{"items":[],"next_cursor":null}')
            response = self.client.get(reverse("videos"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": [], "next_cursor": None})
        self.assertEqual(call.call_args.args, ("content", "/internal/videos"))
        self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {})

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
