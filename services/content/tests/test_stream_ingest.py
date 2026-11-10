from base64 import b64encode
import hashlib
import hmac
import json
import time
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import stream_provider
from service.models import Video
from service.stream_ingest import stream_ingest


class StreamIngestTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.creator = uuid4()
        self.uid = "a" * 32

    def call(self, operation, data, caller="gateway"):
        request = self.factory.post("/internal/videos/stream/" + operation, data,
                                    content_type="application/json")
        request.service_caller = caller
        return stream_ingest(request, operation)

    def intent(self, video, creator=None):
        return self.call("intent", {
            "creator_id": str(creator or self.creator), "video_id": str(video.id),
            "idempotency_key": "local-test-intent-001",
        })

    @patch("service.stream_ingest.stream_provider.create_upload")
    def test_draft_stays_private_and_retries_reserve_once(self, create):
        draft = self.call("draft", {
            "creator_id": str(self.creator), "title": "Original video", "description": "",
        })
        self.assertEqual(draft.status_code, 201)
        video = Video.objects.get(pk=json.loads(draft.content)["id"])
        self.assertEqual((video.visibility, video.state), ("private", "draft"))
        self.assertEqual(self.intent(video, creator=uuid4()).status_code, 404)
        create.assert_not_called()

        create.return_value = (self.uid, "https://upload.videodelivery.net/" + self.uid)
        self.assertEqual(self.intent(video).status_code, 200)
        self.assertEqual(self.intent(video).status_code, 409)
        create.assert_called_once()
        video.refresh_from_db()
        self.assertEqual(video.provider_asset_id, self.uid)
        self.assertEqual(video.visibility, Video.Visibility.PRIVATE)

    @patch("service.stream_ingest.stream_provider.create_upload", side_effect=stream_provider.StreamUnavailable)
    def test_uncertain_provider_result_is_not_retried(self, create):
        video = Video.objects.create(creator_id=self.creator, title="Original")
        self.assertEqual(self.intent(video).status_code, 503)
        self.assertEqual(self.intent(video).status_code, 409)
        create.assert_called_once()

    @patch("service.stream_ingest.stream_provider.asset_is_ready")
    @patch("service.stream_provider._private_value", return_value="fixture-webhook-signing-value")
    def test_callback_requires_signature_and_provider_confirmation(self, secret, ready):
        video = Video.objects.create(creator_id=self.creator, title="Original",
                                     provider_asset_id=self.uid, stream_upload_id=uuid4(), state="uploading")
        raw = json.dumps({"uid": self.uid, "readyToStream": True, "status": {"state": "ready"}}).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(secret.return_value.encode(), timestamp.encode() + b"." + raw,
                             hashlib.sha256).hexdigest()
        envelope = {"body": b64encode(raw).decode("ascii"), "signature": f"time={timestamp},sig1={signature}"}
        self.assertEqual(self.call("webhook", envelope, caller="creators").status_code, 403)
        self.assertEqual(self.call("webhook", envelope | {"signature": "invalid"}).status_code, 403)
        ready.assert_not_called()
        ready.return_value = False
        self.assertEqual(self.call("webhook", envelope).status_code, 503)
        video.refresh_from_db()
        self.assertEqual(video.state, Video.State.UPLOADING)
        ready.return_value = True
        self.assertEqual(self.call("webhook", envelope).status_code, 204)
        video.refresh_from_db()
        self.assertEqual((video.visibility, video.state), ("private", "review"))
        self.assertIsNone(video.published_at)
        ready.reset_mock()
        self.assertEqual(self.call("webhook", envelope).status_code, 204)
        ready.assert_not_called()

    @patch("service.stream_ingest.stream_provider.signed_playback")
    def test_playback_requires_approved_public_publication(self, playback):
        video = Video.objects.create(creator_id=self.creator, title="Original",
                                     provider_asset_id=self.uid, stream_upload_id=uuid4(), state="review")
        request = {"video_id": str(video.id)}
        self.assertEqual(self.call("playback", request).status_code, 404)
        playback.assert_not_called()
        now = timezone.now()
        Video.objects.filter(pk=video.id).update(state="published", visibility="public",
                                                published_at=now, moderation_approved_at=now)
        playback.return_value = "https://customer-fixture.cloudflarestream.com/a.b.c/manifest/video.m3u8"
        self.assertEqual(self.call("playback", request).status_code, 200)
        playback.assert_called_once()
