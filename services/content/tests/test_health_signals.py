"""The read-only health signals measure Content's real audit outbox and stalled-media rule (#145)."""
import json
import sys
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from service.models import AuditDelivery, AuditEvent, MediaUpload, Video

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[2]), *sys.path]):
    from staging_runtime import signals


class HealthSignalTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        AuditDelivery.objects.update(delivered_at=self.now)  # isolate from rows other tests committed

    def event(self, minutes_ago, *, delivered=False, attempts=0):
        event = AuditEvent.objects.create(kind="video.created", subject_type="video", subject_id=uuid4(),
                                          occurred_at=self.now - timedelta(minutes=minutes_ago))
        AuditDelivery.objects.create(event=event, attempts=attempts, delivered_at=self.now if delivered else None)

    def test_audit_backlog_counts_only_undelivered_rows_and_reports_the_oldest(self):
        self.assertEqual(signals.audit_backlog(self.now), {"pending": 0, "oldest_age_seconds": None, "max_attempts": 0})
        self.event(30, delivered=True, attempts=9)
        self.event(12, attempts=3)
        self.event(2)
        self.assertEqual(signals.audit_backlog(self.now), {"pending": 2, "oldest_age_seconds": 720, "max_attempts": 3})

    def test_media_stalled_uses_the_requeue_rule(self):
        self.assertEqual(signals.media_stalled(self.now), {"stalled": 0, "oldest_age_seconds": None})
        for minutes in (60, 3):  # only the first is past the reviewed 15-minute rule
            video = Video.objects.create(creator_id=uuid4(), title="t", state=Video.State.PROCESSING)
            MediaUpload.objects.create(id=uuid4(), video=video, expected_bytes=10, source_etag='"stored"',
                                       expires_at=self.now - timedelta(minutes=minutes))
        self.assertEqual(signals.media_stalled(self.now), {"stalled": 1, "oldest_age_seconds": 3600})

    def test_emitted_line_breaches_only_an_approved_threshold_and_names_no_identifier(self):
        self.event(12)
        out, err = StringIO(), StringIO()
        signals.emit("content", ["audit_backlog"], environ={"KOLOVIBE_ALERT_AUDIT_MAX_AGE_SECONDS": "300"},
                     measure={"audit_backlog": lambda: signals.audit_backlog(self.now)}, out=out, err=err)
        record = json.loads(out.getvalue().removeprefix("KOLOVIBE_SIGNAL "))
        self.assertEqual((record["pending"], record["alert"], record["thresholds"]),
                         (1, True, {"oldest_age_seconds": 300}))
        self.assertTrue(err.getvalue().startswith("KOLOVIBE_ALERT "))
        self.assertNotIn(str(AuditEvent.objects.get().subject_id), out.getvalue())
