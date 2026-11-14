from datetime import datetime, timezone as dt_timezone
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

    def test_owned_library_and_draft_changes_reject_cross_creator_access(self):
        other = Video.objects.create(creator_id=uuid4(), title="Other original")
        owner = {"creator_id": str(self.creator)}
        page = self.call("library", owner | {"cursor": None})
        self.assertEqual(page.status_code, 200)
        self.assertEqual([item["id"] for item in json.loads(page.content)["items"]],
                         [str(self.video.id)])
        self.assertEqual(self.call("library", owner | {"cursor": str(other.id)}).status_code, 400)
        edit = owner | {"video_id": str(self.video.id), "title": "Edited", "description": "Story"}
        self.assertEqual(self.call("edit", edit).status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual((self.video.title, self.video.description), ("Edited", "Story"))
        self.assertEqual(self.call("edit", edit | {"video_id": str(other.id)}).status_code, 404)
        self.assertEqual(self.call("delete", owner | {"video_id": str(other.id)}).status_code, 404)
        self.assertEqual(self.call("delete", owner | {"video_id": str(self.video.id)}).status_code, 200)
        self.assertIsNotNone(Video.objects.get(pk=self.video.id).deleted_at)
        self.assertTrue(Video.objects.filter(pk=other.id).exists())

    def test_owned_detail_includes_state_and_revision_without_cross_creator_access(self):
        other = Video.objects.create(creator_id=uuid4(), title="Other creator", state=Video.State.REMOVED)
        self.video.state = Video.State.REMOVED
        self.video.moderation_revision = 2
        self.video.save(update_fields=["state", "moderation_revision"])
        payload = {"creator_id": str(self.creator), "video_id": str(self.video.id)}
        detail = self.call("detail", payload)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual((json.loads(detail.content)["state"], json.loads(detail.content)["revision"]),
                         ("removed", 2))
        self.assertEqual(self.call("detail", payload | {"video_id": str(other.id)}).status_code, 404)

    def test_reserved_draft_can_be_edited_and_soft_deleted_without_purging_media(self):
        payload = {"creator_id": str(self.creator), "video_id": str(self.video.id)}
        MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
                                   expires_at=timezone.now())
        self.assertEqual(self.call("edit", payload | {"title": "New", "description": ""}).status_code, 200)
        self.assertEqual(self.call("delete", payload).status_code, 200)
        self.assertTrue(MediaUpload.objects.filter(video=self.video).exists())
        self.assertIsNotNone(Video.objects.get(pk=self.video.id).deleted_at)
        self.assertEqual(self.call("detail", payload).status_code, 404)

    def test_owned_library_paginates_without_leaking_another_creators_video(self):
        for index in range(22):
            Video.objects.create(creator_id=self.creator, title=f"Original {index}")
        Video.objects.create(creator_id=uuid4(), title="Other creator")
        payload = {"creator_id": str(self.creator)}
        first = json.loads(self.call("library", payload | {"cursor": None}).content)
        second = json.loads(self.call("library", payload | {"cursor": first["next_cursor"]}).content)
        identifiers = [item["id"] for item in first["items"] + second["items"]]
        self.assertEqual(len(identifiers), 23)
        self.assertEqual(len(set(identifiers)), 23)
        self.assertIsNone(second["next_cursor"])
        self.assertTrue(all(item["creator_id"] == str(self.creator)
                            for item in first["items"] + second["items"]))

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

    @patch("service.media_encoding.render_poster")
    @patch("service.media_storage.put_poster")
    @patch("service.media_storage.put_playback")
    @patch("service.media_encoding.encode")
    @patch("service.media_storage.download_upload")
    @patch("service.media_storage.sign_playback")
    def test_worker_keeps_rendition_private_until_publication(self, sign, download, encode, put, put_poster, render):
        self.video.state = Video.State.PROCESSING
        self.video.save(update_fields=["state"])
        reservation = MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
                                                 expires_at=timezone.now(), source_etag='"object"')
        encode.return_value = 1900
        process(self.video.id)
        process(self.video.id)
        download.assert_called_once()
        put.assert_called_once()
        put_poster.assert_called_once()
        self.assertEqual(render.call_args.args[2:], (1000, 1900))
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility), ("review", "private"))
        self.assertEqual((self.video.duration_seconds, self.video.duration_ms), (2, 1900))
        self.assertTrue(self.video.provider_asset_id.startswith(f"playback/{reservation.id}/"))
        self.assertTrue(self.video.poster_asset_id.endswith(".jpg"))
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

    def _credentials(self, directory):
        paths = {}
        for name in ("KOLOVIBE_R2_ACCESS_KEY_FILE", "KOLOVIBE_R2_SECRET_KEY_FILE"):
            path = Path(directory) / name
            path.touch(mode=0o600)
            path.write_text(secrets.token_hex(32))
            paths[name] = str(path)
        return paths | {"KOLOVIBE_R2_ACCOUNT_ID": "a" * 32, "KOLOVIBE_R2_MEDIA_BUCKET": "local-fixture"}

    def test_presigned_put_binds_all_required_headers_without_network(self):
        with TemporaryDirectory() as directory, patch.dict("os.environ", self._credentials(directory)):
            url = media_storage.sign_upload(f"originals/{uuid4()}.mp4", 1234, 60)
            poster = media_storage.sign_playback(f"playback/{uuid4()}/{uuid4()}.jpg", 300)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["X-Amz-SignedHeaders"], ["content-length;content-type;host;if-none-match"])
        self.assertEqual(query["X-Amz-Expires"], ["60"])
        self.assertEqual(parse_qs(urlsplit(poster).query)["X-Amz-Expires"], ["300"])
        self.assertTrue(urlsplit(poster).path.endswith(".jpg"))
        self.assertEqual(len(query["X-Amz-Signature"][0]), 64)

    def test_signing_is_refused_for_bad_inputs_and_unprotected_credentials(self):
        key = f"originals/{uuid4()}.mp4"
        with TemporaryDirectory() as directory:
            environment = self._credentials(directory)
            with patch.dict("os.environ", environment):
                for bad in (("PUT", "originals/../x.mp4", 60), ("DELETE", key, 60), ("PUT", key, 0),
                            ("PUT", key, 604801), ("PUT", f"other/{uuid4()}.mp4", 60)):
                    with self.subTest(bad), self.assertRaises(media_storage.StorageUnavailable):
                        media_storage._signed_url(bad[0], bad[1], bad[2], {})
                Path(environment["KOLOVIBE_R2_SECRET_KEY_FILE"]).chmod(0o644)
                with self.assertRaises(media_storage.StorageUnavailable):
                    media_storage.sign_upload(key, 10, 60)
            with patch.dict("os.environ", environment | {"KOLOVIBE_R2_ACCOUNT_ID": "short"}):
                with self.assertRaises(media_storage.StorageUnavailable):
                    media_storage.sign_playback(key, 60)

    def test_url_changes_when_any_bound_header_or_expiry_changes(self):
        moment = datetime(2026, 11, 14, 12, 0, tzinfo=dt_timezone.utc)
        key = f"originals/{uuid4()}.mp4"
        with TemporaryDirectory() as directory, patch.dict("os.environ", self._credentials(directory)):
            base = media_storage._signed_url("PUT", key, 60, media_storage.upload_headers(100), moment)
            for other in (media_storage._signed_url("PUT", key, 61, media_storage.upload_headers(100), moment),
                          media_storage._signed_url("PUT", key, 60, media_storage.upload_headers(101), moment),
                          media_storage._signed_url("GET", key, 60, {}, moment)):
                self.assertNotEqual(parse_qs(urlsplit(base).query)["X-Amz-Signature"],
                                    parse_qs(urlsplit(other).query)["X-Amz-Signature"])

    @skipUnless(find_spec("awscrt"), "AWS CRT is the reference signer; install the optional media dependencies")
    def test_pure_python_signature_equals_the_aws_crt_reference(self):
        from awscrt.auth import (AwsCredentialsProvider, AwsSignatureType, AwsSignedBodyValue, AwsSigningConfig,
                                 aws_sign_request)
        from awscrt.http import HttpHeaders, HttpRequest

        moment = datetime(2026, 11, 14, 12, 34, 56, tzinfo=dt_timezone.utc)
        cases = (("PUT", f"originals/{uuid4()}.mp4", 600, media_storage.upload_headers(4321)),
                 ("GET", f"playback/{uuid4()}/{uuid4()}.mp4", 300, {}),
                 ("GET", f"playback/{uuid4()}/{uuid4()}.jpg", 300, {}))
        with TemporaryDirectory() as directory:
            environment = self._credentials(directory)
            access = Path(environment["KOLOVIBE_R2_ACCESS_KEY_FILE"]).read_text().strip()
            secret = Path(environment["KOLOVIBE_R2_SECRET_KEY_FILE"]).read_text().strip()
            with patch.dict("os.environ", environment):
                for method, key, seconds, headers in cases:
                    with self.subTest(method=method, key=key[:9]):
                        ours = media_storage._signed_url(method, key, seconds, headers, moment)
                        host = f"{'a' * 32}.r2.cloudflarestorage.com"
                        request = HttpRequest(method=method, path=f"/local-fixture/{key}",
                                              headers=HttpHeaders([("Host", host), *headers.items()]))
                        config = AwsSigningConfig(
                            signature_type=AwsSignatureType.HTTP_REQUEST_QUERY_PARAMS,
                            credentials_provider=AwsCredentialsProvider.new_static(access, secret),
                            region="auto", service="s3", use_double_uri_encode=False, should_normalize_uri_path=False,
                            signed_body_value=AwsSignedBodyValue.UNSIGNED_PAYLOAD, expiration_in_seconds=seconds,
                            date=moment)
                        reference = aws_sign_request(request, config).result(timeout=5)
                        self.assertEqual(parse_qs(urlsplit(ours).query), parse_qs(urlsplit(reference.path).query))
                        self.assertEqual(urlsplit(ours).path, urlsplit(reference.path).path.split("?")[0])
