"""Decision C slice 2c: Content erases one creator's videos, R2 objects first, and confirms it."""
import json
import uuid
from unittest.mock import patch

from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from service import events, media_storage, privacy
from service.models import (MediaUpload, MetadataRevision, OriginalityAttestation, PrescreenResult, Video)


class Bucket:
    """Holds object names, records deletions; can simulate an outage."""

    def __init__(self, fail=False):
        self.deleted, self.fail, self.objects = [], fail, set()

    def delete_object(self, key):
        if self.fail:
            raise media_storage.StorageUnavailable
        self.deleted.append(key)
        self.objects.discard(key)

    def list_keys(self, prefix):
        if self.fail:
            raise media_storage.StorageUnavailable
        return sorted(key for key in self.objects if key.startswith(prefix))


class ContentErasureTests(TestCase):
    def setUp(self):
        self.person, self.creator, self.other_creator = (str(uuid.uuid4()) for _ in range(3))
        self.request_id = str(uuid.uuid4())
        self.upload = uuid.uuid4()
        self.video = Video.objects.create(
            creator_id=self.creator, title="My song", description="About me", tags=["lagos"], category="hipco",
            state="published", visibility="public", provider_asset_id=f"playback/{self.upload}/{uuid.uuid4()}.mp4",
            poster_asset_id=f"posters/{uuid.uuid4()}/{uuid.uuid4()}.jpg", moderation_approved_at=timezone.now(),
            rights_status="attested")
        MediaUpload.objects.create(id=self.upload, video=self.video, expected_bytes=10,
                                   expires_at=timezone.now())
        OriginalityAttestation.objects.create(upload_id=self.upload, video=self.video, account_id=self.person,
                                              version="v1")
        MetadataRevision.objects.create(video=self.video, proposed={"title": "New title"})
        self.theirs = Video.objects.create(creator_id=self.other_creator, title="Theirs")
        self.bucket = Bucket()
        self.enterContext(patch.object(media_storage, "delete_object", self.bucket.delete_object))
        self.enterContext(patch.object(media_storage, "list_keys", self.bucket.list_keys))

    def payload(self, **changes):
        return {"request_id": self.request_id, "account_id": self.person, "service": "content",
                "creator_id": self.creator} | changes

    def confirmation(self):
        with connection.cursor() as cur:
            cur.execute("SELECT event_type, payload FROM event_outbox")
            rows = cur.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "privacy.erasure_confirmed")
        return json.loads(rows[0][1])

    def test_objects_are_removed_and_the_video_is_emptied_but_evidence_kept(self):
        provider, poster = self.video.provider_asset_id, self.video.poster_asset_id
        self.assertTrue(privacy.erase(str(uuid.uuid4()), self.payload()))
        self.assertEqual(sorted(self.bucket.deleted), sorted([provider, poster, f"originals/{self.upload}.mp4"]))
        self.video.refresh_from_db()
        self.assertEqual((self.video.title, self.video.description, self.video.tags, self.video.category,
                          self.video.state, self.video.visibility, self.video.provider_asset_id,
                          self.video.poster_asset_id), ("", "", [], None, "removed", "private", None, None))
        self.assertIsNotNone(self.video.deleted_at)
        self.assertFalse(MetadataRevision.objects.exists())
        self.assertFalse(MediaUpload.objects.exists())
        self.assertTrue(OriginalityAttestation.objects.filter(video=self.video).exists(), "copyright evidence")
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.title, "Theirs")
        self.assertEqual(self.confirmation(), {
            "request_id": self.request_id, "account_id": self.person, "service": "content",
            "counts": {"media_objects": 3, "metadata_revisions": 1, "upload_records": 1, "videos_emptied": 1},
            "retained": ["attestations"]})

    def test_superseded_renditions_and_posters_are_found_and_removed(self):
        old_rendition = f"playback/{self.upload}/{uuid.uuid4()}.mp4"
        old_frame = f"playback/{self.upload}/{uuid.uuid4()}.jpg"
        old_poster = f"posters/{self.video.id}/{uuid.uuid4()}.jpg"
        someone_elses = f"playback/{uuid.uuid4()}/{uuid.uuid4()}.mp4"
        self.bucket.objects |= {old_rendition, old_frame, old_poster, someone_elses, self.video.provider_asset_id}
        privacy.erase(str(uuid.uuid4()), self.payload())
        self.assertTrue({old_rendition, old_frame, old_poster} <= set(self.bucket.deleted))
        self.assertEqual(self.bucket.objects, {someone_elses}, "only this creator's objects are touched")
        self.assertEqual(len(self.bucket.deleted), len(set(self.bucket.deleted)), "nothing is deleted twice")
        confirmation = self.confirmation()
        self.assertEqual(confirmation["counts"]["media_objects"], 6)
        self.assertNotIn("untracked_media", confirmation["retained"])

    def test_an_object_it_may_not_delete_keeps_untracked_media_retained(self):
        self.bucket.objects.add(f"playback/{self.upload}/unexpected-name.mov")
        privacy.erase(str(uuid.uuid4()), self.payload())
        self.assertIn("untracked_media", self.confirmation()["retained"])
        self.assertIn(f"playback/{self.upload}/unexpected-name.mov", self.bucket.objects)

    def test_a_listing_outage_records_nothing_so_the_task_retries(self):
        def down(prefix):
            raise media_storage.StorageUnavailable

        with patch.object(media_storage, "list_keys", down), self.assertRaises(media_storage.StorageUnavailable):
            privacy.erase(str(uuid.uuid4()), self.payload())
        with connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM event_inbox")
            self.assertEqual(cur.fetchone()[0], 0)

    def test_a_storage_outage_records_nothing_so_the_task_retries(self):
        self.bucket.fail = True
        with self.assertRaises(media_storage.StorageUnavailable):
            privacy.erase(str(uuid.uuid4()), self.payload())
        self.video.refresh_from_db()
        self.assertEqual(self.video.title, "My song")
        with connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM event_inbox")
            self.assertEqual(cur.fetchone()[0], 0)

    def test_a_repeat_delivery_never_touches_storage_again(self):
        event = str(uuid.uuid4())
        privacy.erase(event, self.payload())
        self.bucket.deleted.clear()
        self.assertFalse(privacy.erase(event, self.payload()))
        self.assertEqual(self.bucket.deleted, [])

    def test_someone_never_a_creator_has_no_videos_to_erase(self):
        PrescreenResult.objects.create(upload_id=uuid.uuid4(), video=self.video, source_sha256="a" * 64,
                                       disposition="clear")
        privacy.erase(str(uuid.uuid4()), self.payload(creator_id=None))
        self.assertEqual(self.bucket.deleted, [])
        confirmation = self.confirmation()
        self.assertEqual(set(confirmation["counts"].values()), {0})
        self.assertEqual(confirmation["retained"], ["attestations"], "their own attestation is still evidence")

    def test_malformed_requests_are_refused_before_any_change(self):
        for bad in (self.payload(service="creators"), self.payload(creator_id="nope"), self.payload(extra=1),
                    {"request_id": self.request_id, "account_id": self.person, "service": "content"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.erase(str(uuid.uuid4()), bad)
        self.assertEqual(self.bucket.deleted, [])

    def test_only_confirmations_may_enter_the_outbox(self):
        with transaction.atomic():
            for kind, payload in (("privacy.erasure_requested", {"service": "content"}),
                                  ("privacy.erasure_confirmed", {"service": "creators"})):
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    events.record_event(kind, payload)


class StorageDeleteTests(SimpleTestCase):
    def credentials(self, directory):
        from pathlib import Path

        values = {}
        for name, value in (("KOLOVIBE_R2_ACCESS_KEY_FILE", "AKIAEXAMPLEKEY12345"),
                            ("KOLOVIBE_R2_SECRET_KEY_FILE", "example-secret-value-1234567890")):  # pragma: allowlist secret
            path = Path(directory) / name
            path.write_text(value)
            path.chmod(0o600)
            values[name] = str(path)
        return values | {"KOLOVIBE_R2_ACCOUNT_ID": "1" * 32, "KOLOVIBE_R2_MEDIA_BUCKET": "kolovibe-media"}

    def test_the_worker_can_sign_its_own_delete_and_list_but_never_a_client_url_for_them(self):
        from tempfile import TemporaryDirectory
        from urllib.parse import parse_qs, urlsplit

        key = f"originals/{uuid.uuid4()}.mp4"
        prefix = f"playback/{uuid.uuid4()}/"
        with TemporaryDirectory() as directory, patch.dict("os.environ", self.credentials(directory)):
            self.assertIn(f"/kolovibe-media/{key}?", media_storage._signed_url("DELETE", key, 60, {}, internal=True))
            with self.assertRaises(media_storage.StorageUnavailable):
                media_storage._signed_url("DELETE", key, 60, {})
            listing = urlsplit(media_storage._signed_list_url(prefix, "abc+/="))
            query = parse_qs(listing.query)
            self.assertEqual(listing.path, "/kolovibe-media")
            self.assertEqual((query["list-type"], query["prefix"], query["continuation-token"]), (["2"], [prefix], ["abc+/="]))
            self.assertEqual(len(query["X-Amz-Signature"][0]), 64)
            for bad in ("", "playback/", "originals/", f"playback/{uuid.uuid4()}", f"posters/{uuid.uuid4()}/x/",
                        "playback/../", f"other/{uuid.uuid4()}/"):
                with self.subTest(bad), self.assertRaises(media_storage.StorageUnavailable):
                    media_storage._signed_list_url(bad)
            with self.assertRaises(media_storage.StorageUnavailable):
                media_storage._signed_list_url(prefix, "bad token")

    def test_listing_follows_pages_and_refuses_anything_unexpected(self):
        from contextlib import contextmanager

        prefix = f"posters/{uuid.uuid4()}/"
        first, second = prefix + f"{uuid.uuid4()}.jpg", prefix + f"{uuid.uuid4()}.jpg"
        pages = {None: f"<Key>{first}</Key><IsTruncated>true</IsTruncated><NextContinuationToken>t1</NextContinuationToken>",
                 "t1": f"<Key>{second}</Key><IsTruncated>false</IsTruncated>"}

        class Response:
            def __init__(self, text):
                self.text = text

            def read(self, limit):
                return self.text if isinstance(self.text, bytes) else self.text.encode()

        def fake(responses):
            @contextmanager
            def request(method, key, headers=None, body=None, *, url=None):
                self.assertEqual((method, key), ("GET", ""))
                yield Response(responses(url))
            return request

        def by_token(url):
            from urllib.parse import parse_qs, urlsplit

            return pages[parse_qs(urlsplit(url).query).get("continuation-token", [None])[0]]

        with patch("service.media_storage._signed_list_url", lambda p, t=None: "https://x/?" + ("continuation-token=" + t if t else "")), \
                patch("service.media_storage._request", fake(by_token)):
            self.assertEqual(media_storage.list_keys(prefix), [first, second])
        for text in (f"<Key>playback/{uuid.uuid4()}/x.mp4</Key>",                      # outside the prefix
                     f"<Key>{first}</Key><IsTruncated>true</IsTruncated>",                 # truncated, no token
                     b"<Key>\xff</Key>"):
            with self.subTest(text), patch("service.media_storage._signed_list_url", lambda p, t=None: "https://x/"), \
                    patch("service.media_storage._request", fake(lambda url, t=text: t)), \
                    self.assertRaises(media_storage.StorageUnavailable):
                media_storage.list_keys(prefix)
        endless = f"<Key>{first}</Key><IsTruncated>true</IsTruncated><NextContinuationToken>t</NextContinuationToken>"
        with patch("service.media_storage._signed_list_url", lambda p, t=None: "https://x/"), \
                patch("service.media_storage._request", fake(lambda url: endless)), \
                self.assertRaises(media_storage.StorageUnavailable):
            media_storage.list_keys(prefix)

    def test_delete_is_signed_and_a_missing_object_counts_as_removed(self):
        key = f"originals/{uuid.uuid4()}.mp4"
        with patch("service.media_storage._request") as request:
            media_storage.delete_object(key)
        self.assertEqual(request.call_args.args, ("DELETE", key))
        with patch("service.media_storage._request", side_effect=media_storage.ObjectMissing):
            media_storage.delete_object(key)
        with patch("service.media_storage._request", side_effect=media_storage.StorageUnavailable), \
                self.assertRaises(media_storage.StorageUnavailable):
            media_storage.delete_object(key)


@override_settings(LOCAL_MEDIA_ENABLED=True)
class ContentWorkerTests(SimpleTestCase):
    def test_worker_accepts_only_erasure_requests_and_retries_outages(self):
        with patch.dict("os.environ", {"KOLOVIBE_RABBITMQ_URL": "amqps://u:p@localhost:5671/kv"}):
            from service import media_tasks
        with self.assertRaises(ValueError):
            media_tasks.receive_event.run(str(uuid.uuid4()), "privacy.erasure_confirmed", {})
        with patch("service.privacy.erase", return_value=True) as erase:
            self.assertTrue(media_tasks.receive_event.run("e", "privacy.erasure_requested", {"a": 1}))
        erase.assert_called_once_with("e", {"a": 1})
        with patch("service.privacy.erase", side_effect=media_storage.StorageUnavailable), \
                patch.object(media_tasks.receive_event, "retry", side_effect=RuntimeError("retry")) as retry, \
                self.assertRaises(RuntimeError):
            media_tasks.receive_event.run("e", "privacy.erasure_requested", {"a": 1})
        retry.assert_called_once()

    def test_confirmations_go_to_identity_through_its_named_exchange(self):
        task_name, queue, options = events._destination()
        self.assertEqual((task_name, options), ("kolovibe.identity.event",
                                                {"exchange": "kolovibe.identity", "routing_key": "kolovibe.identity"}))
        self.assertTrue(queue.no_declare)
