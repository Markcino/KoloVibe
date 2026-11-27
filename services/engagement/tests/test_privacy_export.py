"""Mandate 3.3: Engagement assembles one account's own engagement records for an access export, once."""
import json
import uuid
from unittest.mock import patch

from django.test import TestCase

from service import privacy
from service.models import FraudHold, VideoLike
from .test_privacy_erasure import EngagementErasureTests


class EngagementExportTests(TestCase):
    setUp = EngagementErasureTests.setUp
    payload = EngagementErasureTests.payload

    def test_assembles_only_this_account_and_changes_nothing(self):
        FraudHold.objects.create(account_id=self.person, video_id=self.video, reason_code="X")
        self.assertTrue(privacy.export(str(uuid.uuid4()), self.payload()))
        event_type, part = self.recorded.call_args.args
        self.assertEqual(event_type, "privacy.export_delivered")
        self.assertEqual(set(part), {"request_id", "account_id", "service", "data", "withheld", "truncated"})
        self.assertEqual((part["request_id"], part["account_id"], part["service"]),
                         (self.request_id, self.person, "engagement"))
        self.assertEqual({name: len(rows) for name, rows in part["data"].items()},
                         {"likes": 1, "follows": 1, "shares": 1, "watch_sessions": 1, "qualified_watches": 1})
        self.assertEqual(part["data"]["likes"][0]["video_id"], str(self.video))
        self.assertEqual((part["withheld"], part["truncated"]), (["fraud_holds"], []))
        self.assertNotIn(self.other, json.dumps(part), "another account's rows never appear")
        json.dumps(part, allow_nan=False)  # plain JSON only
        self.assertEqual(VideoLike.objects.count(), 2, "an export deletes nothing")

    def test_a_repeat_delivery_sends_nothing(self):
        self.accepted.return_value = False
        self.assertFalse(privacy.export(str(uuid.uuid4()), self.payload()))
        self.recorded.assert_not_called()

    def test_a_category_over_the_row_limit_is_cut_and_named(self):
        with patch.object(privacy, "EXPORT_ROW_LIMIT", 0):
            privacy.export(str(uuid.uuid4()), self.payload())
        part = self.recorded.call_args.args[1]
        self.assertEqual(part["truncated"], ["likes", "follows", "shares", "watch_sessions", "qualified_watches"])
        self.assertEqual(part["withheld"], [])

    def test_malformed_requests_are_refused(self):
        for bad in (self.payload(service="points"), self.payload(account_id="nope"), self.payload(extra=1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.export(str(uuid.uuid4()), bad)
        self.accepted.assert_not_called()

    def test_the_worker_routes_export_requests(self):
        with patch.dict("os.environ", {"KOLOVIBE_ENV": "local",
                                       "KOLOVIBE_RABBITMQ_URL": "amqps://u:p@localhost:5671/kv"}):
            from service import celery_app
        with patch("service.privacy.export", return_value=True) as export:
            self.assertTrue(celery_app.receive_event.run("e", "privacy.export_requested", {"a": 1}))
        export.assert_called_once_with("e", {"a": 1})
