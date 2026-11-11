from datetime import UTC, datetime, timedelta
import json
from unittest.mock import patch
from uuid import uuid4

from django.db import DatabaseError
from django.test import RequestFactory, TestCase

from service.models import QualifiedWatch, WatchSession
from service.watch import watch_api


class WatchTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.now = datetime(2026, 11, 10, 18, tzinfo=UTC)
        self.clock = self.enterContext(patch("service.watch.timezone.now", side_effect=lambda: self.now))
        self.event = self.enterContext(patch("service.watch.record_event"))
        self.asset = {"account_id": str(uuid4()), "video_id": str(uuid4()),
                      "creator_user_id": str(uuid4()), "duration_ms": 2501, "revision": 1}

    def call(self, operation, data, caller="gateway"):
        request = self.factory.post("/internal/watch", data, content_type="application/json")
        request.service_caller = caller
        return watch_api(request, operation)

    def start(self):
        response = self.call("start", self.asset)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)["session_id"]

    def progress(self, session_id, position_ms, **override):
        return self.call("progress", self.asset | {
            "session_id": session_id, "position_ms": position_ms,
        } | override)

    def test_short_threshold_and_idempotent_retry(self):
        session = self.start()
        self.assertEqual(self.start(), session)
        self.now += timedelta(milliseconds=2000)
        self.assertEqual(json.loads(self.progress(session, 2001).content), {"qualified": False})
        self.now += timedelta(milliseconds=1)
        self.assertEqual(json.loads(self.progress(session, 2001).content), {"qualified": True})
        self.assertEqual(json.loads(self.progress(session, 2001).content), {"qualified": True})
        self.event.assert_called_once_with("dec003.qualified_view", {
            "creator_user_id": self.asset["creator_user_id"], "qualified_at": self.now.isoformat(),
        })
        self.now += timedelta(hours=23)
        newer = self.start()
        self.assertNotEqual(newer, session)
        self.now += timedelta(seconds=3)
        self.progress(newer, 2501)
        self.assertEqual(self.event.call_count, 1)
        self.now += timedelta(hours=1)
        newest = self.start()
        self.now += timedelta(seconds=3)
        self.progress(newest, 2501)
        self.assertEqual(self.event.call_count, 2)

    def test_long_video_cannot_qualify_before_thirty_seconds(self):
        self.asset["duration_ms"] = 90_000
        session = self.start()
        for second in range(3, 30, 3):
            self.now += timedelta(seconds=3)
            self.assertEqual(json.loads(self.progress(session, second * 1000).content), {"qualified": False})
        self.now += timedelta(seconds=3)
        self.assertEqual(json.loads(self.progress(session, 30_000).content), {"qualified": True})
        self.event.assert_called_once()

    def test_wrong_account_revision_and_impossible_progress(self):
        self.assertEqual(self.call("start", self.asset, caller="content").status_code, 403)
        self.assertEqual(self.call("start", self.asset | {"account_id": self.asset["creator_user_id"]}).status_code, 403)
        session = self.start()
        self.assertEqual(self.progress(session, 1, account_id=str(uuid4())).status_code, 404)
        self.assertEqual(self.progress(session, 1, revision=2).status_code, 409)
        self.assertEqual(self.progress(session, 2501).status_code, 409)
        self.now += timedelta(seconds=3)
        self.assertEqual(self.progress(session, 2501).status_code, 409)
        self.event.assert_not_called()

    def test_outbox_failure_rolls_back_qualification(self):
        session = self.start()
        self.now += timedelta(seconds=3)
        self.event.side_effect = DatabaseError
        self.assertEqual(self.progress(session, 2501).status_code, 503)
        self.assertIsNone(WatchSession.objects.get().qualified_at)
        self.assertFalse(QualifiedWatch.objects.exists())
        self.event.side_effect = None
        self.assertEqual(json.loads(self.progress(session, 2501).content), {"qualified": True})

    def test_qualification_and_watch_time_are_server_owned_and_survive_session_renewal(self):
        session = self.start()
        self.now += timedelta(milliseconds=2100)
        self.assertEqual(json.loads(self.progress(session, 2100).content), {"qualified": True})
        self.assertEqual(QualifiedWatch.objects.get().watched_ms, 2100)
        self.now += timedelta(milliseconds=401)
        self.progress(session, 2501)
        self.assertEqual(QualifiedWatch.objects.get().watched_ms, 2501)
        self.now += timedelta(hours=25)
        renewed = self.start()
        self.now += timedelta(milliseconds=2501)
        self.progress(renewed, 2501)
        self.assertEqual(QualifiedWatch.objects.count(), 2)
        self.assertEqual(self.event.call_count, 2)

    def test_clients_cannot_submit_qualification_points_or_a_watch_timestamp(self):
        for field, value in (("qualified", True), ("points", 999), ("qualified_at", self.now.isoformat()),
                             ("watched_ms", 30000), ("amount", 1)):
            self.assertEqual(self.call("start", self.asset | {field: value}).status_code, 400)
        self.assertEqual(self.call("start", self.asset, caller="identity").status_code, 403)
        self.assertFalse(WatchSession.objects.exists())
        self.assertFalse(QualifiedWatch.objects.exists())
        self.event.assert_not_called()

    def test_late_duplicate_progress_cannot_invalidate_qualified_session(self):
        session = self.start()
        self.now += timedelta(seconds=3)
        self.assertEqual(json.loads(self.progress(session, 2501).content), {"qualified": True})
        self.now += timedelta(seconds=30)
        self.assertEqual(json.loads(self.progress(session, 2501).content), {"qualified": True})
        self.assertFalse(WatchSession.objects.get().invalidated)
        self.event.assert_called_once()
