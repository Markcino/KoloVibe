import json
from uuid import uuid4
from unittest.mock import patch

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service.stream_ingest import issue_video_upload, video_playback
from .test_videos import Response


class StreamGatewayTests(SimpleTestCase):
    @patch("service.stream_ingest.signed_internal_request")
    @patch("service.stream_ingest.creator_eligibility")
    def test_upload_uses_creator_service_decision(self, eligibility, content):
        factory = RequestFactory()
        video_id, creator_id, upload_id = uuid4(), uuid4(), uuid4()
        request = factory.post("/upload", data=b"", content_type="application/json", HTTP_IDEMPOTENCY_KEY="local-test-intent-001")
        eligibility.return_value = JsonResponse({"upload_eligible": False, "creator_id": None})
        self.assertEqual(issue_video_upload(request, video_id).status_code, 403)
        content.assert_not_called()
        eligibility.return_value = JsonResponse({"upload_eligible": True, "creator_id": str(creator_id)})
        content.return_value = Response(json.dumps({
            "video_id": str(video_id), "upload_id": str(upload_id),
            "upload_url": "https://upload.videodelivery.net/" + "a" * 32,
            "expires_at": "2026-11-10T18:45:00+00:00", "max_bytes": 200_000_000,
        }).encode())
        response = issue_video_upload(request, video_id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(json.loads(content.call_args.kwargs["payload"])["creator_id"], str(creator_id))

    @patch("service.stream_ingest.signed_internal_request")
    def test_anonymous_playback_is_denied_without_provider_call(self, content):
        self.assertEqual(video_playback(RequestFactory().get("/playback"), uuid4()).status_code, 401)
        content.assert_not_called()
