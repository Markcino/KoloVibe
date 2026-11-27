"""Mandate 3.3b: Content assembles one creator's own video records for an access export, once."""
import json
import uuid

from django.db import connection, transaction
from unittest.mock import patch

from django.test import TestCase, override_settings

from service import privacy
from service.models import PrescreenResult, Video
from . import test_privacy_erasure


def delivered(self):
    with connection.cursor() as cur:
        cur.execute("SELECT event_type, payload FROM event_outbox")
        rows = cur.fetchall()
    self.assertEqual(len(rows), 1)
    self.assertEqual(rows[0][0], "privacy.export_delivered")
    part = json.loads(rows[0][1])
    json.dumps(part, allow_nan=False)
    return part


def export_twice(self, payload):
    event = str(uuid.uuid4())
    with transaction.atomic():
        self.assertTrue(privacy.export(event, payload))
    with transaction.atomic():
        self.assertFalse(privacy.export(event, payload), "a repeat delivery sends nothing more")
    return delivered(self)


class ContentExportTests(TestCase):
    setUp = test_privacy_erasure.ContentErasureTests.setUp
    payload = test_privacy_erasure.ContentErasureTests.payload

    def test_assembles_the_creators_videos_without_storage_keys_and_touches_no_object(self):
        PrescreenResult.objects.create(upload_id=self.upload, video=self.video, source_sha256="a" * 64,
                                       fingerprint_sha256="b" * 64, reasons=[], disposition="clear")
        part = export_twice(self, self.payload())
        self.assertEqual({name: len(rows) for name, rows in part["data"].items()},
                         {"videos": 1, "metadata_revisions": 1, "uploads": 1, "attestations": 1})
        video = part["data"]["videos"][0]
        self.assertEqual((video["title"], video["tags"]), ("My song", ["lagos"]))
        self.assertEqual(json.loads(part["data"]["metadata_revisions"][0]["proposed"]), {"title": "New title"})
        text = json.dumps(part)
        for hidden in (self.video.provider_asset_id, self.video.poster_asset_id, "Theirs"):
            self.assertNotIn(hidden, text)
        self.assertEqual(part["withheld"], ["media_files", "prescreen_results"])
        self.assertEqual(self.bucket.deleted, [], "an export never touches storage")
        self.assertEqual(Video.objects.get(pk=self.video.pk).title, "My song")

    def test_someone_who_was_never_a_creator_still_gets_their_attestations_only(self):
        part = export_twice(self, self.payload(creator_id=None))
        self.assertEqual({name: len(rows) for name, rows in part["data"].items()},
                         {"videos": 0, "metadata_revisions": 0, "uploads": 0, "attestations": 1})

    @override_settings(LOCAL_MEDIA_ENABLED=True)
    def test_the_media_worker_routes_export_requests(self):
        with patch.dict("os.environ", {"KOLOVIBE_RABBITMQ_URL": "amqps://u:p@localhost:5671/kv"}):
            from service import media_tasks
        with patch("service.privacy.export", return_value=True) as export:
            self.assertTrue(media_tasks.receive_event.run("e", "privacy.export_requested", {"a": 1}))
        export.assert_called_once_with("e", {"a": 1})
        with self.assertRaises(ValueError):
            media_tasks.receive_event.run("e", "privacy.export_delivered", {})
