from importlib.util import find_spec
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import media_encoding, media_storage
from service.media_api import media_api
from service.media_processing import process
from service.models import MediaUpload, Video


class R2MediaTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.creator = uuid4()
        self.video = Video.objects.create(creator_id=self.creator, title="Original")

    def call(self, operation, data):
        request = self.factory.post("/internal/videos/media/" + operation, data, content_type="application/json")
        request.service_caller = "gateway"
        return media_api(request, operation)

    @patch("service.media_api._enqueue")
    @patch("service.media_storage.inspect_upload")
    @patch("service.media_storage.sign_upload", return_value="https://example.invalid/upload")
    def test_upload_confirmation_retries_same_reservation(self, sign, inspect, enqueue):
        payload = {"video_id": str(self.video.id), "creator_id": str(self.creator)}
        intent = payload | {"size_bytes": 1234, "idempotency_key": "local-test-media-001"}
        first = self.call("intent", intent)
        second = self.call("intent", intent)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(json.loads(first.content)["upload_id"], json.loads(second.content)["upload_id"])
        self.assertEqual(self.call("intent", intent | {"size_bytes": 1}).status_code, 409)
        self.assertEqual(self.call("intent", intent | {"creator_id": str(uuid4())}).status_code, 404)
        self.assertEqual(MediaUpload.objects.count(), 1)
        inspect.return_value = (1235, "video/mp4", '"example"')
        self.assertEqual(self.call("complete", payload).status_code, 409)
        enqueue.assert_not_called()
        inspect.return_value = (1234, "video/mp4", '"example"')
        enqueue.side_effect = OSError
        self.assertEqual(self.call("complete", payload).status_code, 503)
        self.video.refresh_from_db()
        self.assertEqual(self.video.state, Video.State.PROCESSING)
        enqueue.side_effect = None
        self.assertEqual(self.call("complete", payload).status_code, 202)
        self.assertEqual(MediaUpload.objects.get().source_etag, '"example"')

    @patch("service.media_storage.put_playback")
    @patch("service.media_encoding.encode")
    @patch("service.media_storage.download_upload")
    @patch("service.media_storage.sign_playback")
    def test_worker_keeps_rendition_private_until_publication(self, sign, download, encode, put):
        self.video.state = Video.State.PROCESSING
        self.video.save(update_fields=["state"])
        reservation = MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
                                                 expires_at=timezone.now(), source_etag='"object"')
        encode.return_value = 1900
        process(self.video.id)
        process(self.video.id)
        download.assert_called_once()
        put.assert_called_once()
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility), ("review", "private"))
        self.assertEqual((self.video.duration_seconds, self.video.duration_ms), (2, 1900))
        self.assertTrue(self.video.provider_asset_id.startswith(f"playback/{reservation.id}/"))
        self.assertEqual(self.call("playback", {"video_id": str(self.video.id)}).status_code, 404)
        sign.assert_not_called()
        now = timezone.now()
        Video.objects.filter(pk=self.video.pk).update(state="published", visibility="public",
                                                     published_at=now, moderation_approved_at=now)
        sign.return_value = "https://example.invalid/playback"
        self.assertEqual(self.call("playback", {"video_id": str(self.video.id)}).status_code, 200)
        response = self.call("watch-check", {"video_id": str(self.video.id)})
        self.assertEqual(json.loads(response.content), {
            "creator_id": str(self.creator), "duration_ms": 1900, "revision": 0,
        })
        sign.assert_called_once()

    @patch("service.media_encoding.encode", side_effect=media_encoding.InvalidMedia)
    @patch("service.media_storage.download_upload")
    def test_invalid_media_is_failed_without_a_playback_key(self, download, encode):
        self.video.state = Video.State.PROCESSING
        self.video.save(update_fields=["state"])
        MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
                                   expires_at=timezone.now(), source_etag='"object"')
        process(self.video.id)
        self.video.refresh_from_db()
        self.assertEqual(self.video.state, Video.State.FAILED)
        self.assertIsNone(self.video.provider_asset_id)

    @skipUnless(find_spec("awscrt"), "Install the optional media dependencies")
    def test_crt_presigned_put_binds_all_required_headers_without_network(self):
        with TemporaryDirectory() as directory:
            paths = {}
            for name in ("KOLOVIBE_R2_ACCESS_KEY_FILE", "KOLOVIBE_R2_SECRET_KEY_FILE"):
                path = Path(directory) / name
                path.touch(mode=0o600)
                path.write_text(secrets.token_hex(32))
                paths[name] = str(path)
            with patch.dict("os.environ", paths | {
                "KOLOVIBE_R2_ACCOUNT_ID": "a" * 32, "KOLOVIBE_R2_MEDIA_BUCKET": "local-fixture",
            }):
                url = media_storage.sign_upload(f"originals/{uuid4()}.mp4", 1234, 60)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["X-Amz-SignedHeaders"], ["content-length;content-type;host;if-none-match"])
        self.assertEqual(query["X-Amz-Expires"], ["60"])
