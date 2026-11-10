from datetime import UTC, datetime, timedelta
import json
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.models import DailyAwardCount, PointsEntry
from service.pilot_points import apply_qualified_view, points_read


class PointsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account = uuid4()
        self.creator = uuid4()
        self.now = datetime(2026, 11, 10, 23, 59, tzinfo=UTC)
        self.enterContext(patch("service.pilot_points.timezone.now", side_effect=lambda: self.now))

    def apply(self, event_id=None, account=None, timestamp=None):
        return apply_qualified_view(event_id or uuid4(), {
            "creator_user_id": str(account or self.account), "qualified_at": (timestamp or self.now).isoformat(),
        })

    def read(self, operation, caller="gateway", account=None, **data):
        request = self.factory.post("/internal/points/" + operation, {
            "account_id": str(account or self.account), "creator_id": str(self.creator), **data,
        }, content_type="application/json")
        request.service_caller = caller
        return points_read(request, operation)

    def test_duplicate_and_utc_daily_cap(self):
        seen = set()

        def accept(event, _):
            if event in seen:
                return False
            seen.add(event)
            return True

        with patch("service.pilot_points.accept_once", side_effect=accept):
            DailyAwardCount.objects.create(creator_user_id=self.account, day=self.now.date(), awards=99)
            event = uuid4()
            self.assertTrue(self.apply(event))
            self.assertFalse(self.apply(event))
            denied = uuid4()
            self.assertFalse(self.apply(denied))
            previous = self.now
            self.now += timedelta(minutes=1)
            self.assertFalse(self.apply(denied, timestamp=previous))
            self.assertTrue(self.apply())
            self.assertTrue(self.apply(account=uuid4(), timestamp=previous))
        self.assertEqual(json.loads(self.read("balance").content)["balance"], 2)
        self.assertEqual(PointsEntry.objects.count(), 3)

    @patch("service.pilot_points.accept_once", return_value=True)
    def test_private_paginated_history(self, _):
        for _ in range(21):
            self.apply()
        other = uuid4()
        self.apply(account=other)
        response = self.read("entries", cursor=None)
        first = json.loads(response.content)
        self.assertEqual(len(first["items"]), 20)
        second = json.loads(self.read("entries", cursor=first["next_cursor"]).content)
        self.assertEqual(len(second["items"]), 1)
        self.assertIsNone(second["next_cursor"])
        self.assertEqual(self.read("entries", cursor=first["next_cursor"], account=other).status_code, 400)
        self.assertEqual(self.read("balance", caller="engagement").status_code, 403)
