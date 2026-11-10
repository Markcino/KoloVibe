from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from service import stream_provider


class CloudflareStreamTests(SimpleTestCase):
    @patch("service.stream_provider._call")
    def test_direct_upload_sets_privacy_expiry_duration_and_binding(self, call):
        video_id = uuid4()
        expires_at = datetime(2026, 11, 10, 18, 45, tzinfo=timezone.utc)
        uid = "a" * 32
        url = "https://upload.videodelivery.net/" + uid
        call.return_value = {"uid": uid, "uploadURL": url}
        self.assertEqual(stream_provider.create_upload(video_id, expires_at), (uid, url))
        call.assert_called_once_with("POST", "direct_upload", {
            "expiry": expires_at.isoformat(), "maxDurationSeconds": 300,
            "requireSignedURLs": True, "meta": {"kolovibe_video_id": str(video_id)},
        })
        call.return_value = {"uid": uid, "uploadURL": "https://example.invalid/" + uid}
        with self.assertRaises(stream_provider.StreamUnavailable):
            stream_provider.create_upload(video_id, expires_at)

    @patch("service.stream_provider._call")
    def test_status_check_requires_private_bound_asset(self, call):
        uid, video_id = "a" * 32, uuid4()
        call.return_value = {"uid": uid, "requireSignedURLs": True, "meta": {"kolovibe_video_id": str(video_id)},
                             "readyToStream": True, "status": {"state": "ready"}}
        self.assertTrue(stream_provider.asset_is_ready(uid, video_id))
        call.return_value["requireSignedURLs"] = False
        with self.assertRaises(stream_provider.StreamUnavailable):
            stream_provider.asset_is_ready(uid, video_id)
