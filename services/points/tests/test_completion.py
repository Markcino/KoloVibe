from datetime import timedelta
import json
from unittest.mock import patch
from uuid import uuid4

from django.db import DatabaseError
from django.test import TestCase

from service.models import DailyAwardCount, PointsEntry, QualificationReceipt
from . import test_pilot_points as fixtures


class PointsCompletionTests(TestCase):
    setUp = fixtures.PointsTests.setUp
    apply = fixtures.PointsTests.apply
    read = fixtures.PointsTests.read
    @patch("service.pilot_points.accept_once", return_value=True)
    def test_pending_receipt_survives_failed_post_and_retry_posts_once(self, accept):
        ident = uuid4()
        with patch("service.pilot_points.PointsEntry.objects.create", side_effect=DatabaseError):
            with self.assertRaises(DatabaseError):
                self.apply(ident)
        pending = json.loads(self.read("balance").content)
        self.assertEqual((pending["pending"], pending["confirmed"], pending["balance"]), (1, 0, 0))
        self.assertEqual(PointsEntry.objects.count(), 0)
        self.assertEqual(DailyAwardCount.objects.count(), 0)
        self.assertEqual(json.loads(self.read("entry", entry_id=str(ident)).content)["status"], "pending")
        self.assertTrue(self.apply(ident))
        self.assertFalse(self.apply(ident))
        self.assertEqual(PointsEntry.objects.count(), 1)
        self.assertEqual(json.loads(self.read("entry", entry_id=str(ident)).content)["status"], "confirmed")
        self.assertEqual(QualificationReceipt.objects.get(pk=ident).status, "posted")
        self.assertEqual(json.loads(self.read("balance").content)["pending"], 0)

    @patch("service.pilot_points.accept_once", return_value=True)
    def test_real_cap_receipts_reversals_and_filters(self, accept):
        self.apply()
        award = PointsEntry.objects.get()
        PointsEntry.objects.create(creator_user_id=self.account, entry_type="REVERSAL", delta=-1,
                                  reversal_of=award, reason_code="REVIEWED", rule_version="DEC-003-v1")
        PointsEntry.objects.create(creator_user_id=self.account, entry_type="ADJUSTMENT", delta=2,
                                  reason_code="REVIEWED", rule_version="DEC-003-v1", video_id=uuid4())
        DailyAwardCount.objects.update(awards=100)
        ident = uuid4()
        self.assertFalse(self.apply(ident))
        self.assertFalse(self.apply(ident))
        balance = json.loads(self.read("balance").content)
        self.assertEqual({k: balance[k] for k in ("balance", "confirmed", "pending", "withheld", "reversed")},
                         {"balance": 2, "confirmed": 1, "pending": 0, "withheld": 1, "reversed": 1})
        for status, count in (("all", 4), ("confirmed", 1), ("pending", 0), ("adjustments", 2)):
            page = json.loads(self.read("entries", cursor=None, status=status).content)
            self.assertEqual(len(page["items"]), count)
            self.assertTrue(all("status" in item and "video_id" in item for item in page["items"]))
            if status != "all":
                self.assertTrue(all(item["status"] == status for item in page["items"]))
        self.assertEqual(self.read("entry", entry_id=str(award.pk), account=uuid4()).status_code, 404)
        self.assertEqual(self.read("entry", entry_id=str(ident), account=uuid4()).status_code, 404)
        self.assertEqual(self.read("entries", cursor=None, status="invented").status_code, 400)
        self.assertEqual(QualificationReceipt.objects.get(pk=ident).reason_code, "DAILY_CAP")

    @patch("service.pilot_points.accept_once", return_value=True)
    def test_mixed_receipt_ledger_pagination_has_no_loss_or_duplicates(self, accept):
        for _ in range(15):
            self.apply()
        for _ in range(9):
            QualificationReceipt.objects.create(id=uuid4(), creator_user_id=self.account, qualified_at=self.now)
        first = json.loads(self.read("entries", cursor=None).content)
        second = json.loads(self.read("entries", cursor=first["next_cursor"]).content)
        self.assertEqual(len(first["items"]), 20)
        self.assertEqual(len(second["items"]), 4)
        self.assertEqual(len({row["id"] for row in first["items"] + second["items"]}), 24)
        self.assertIsNone(second["next_cursor"])

    @patch("service.pilot_points.accept_once", return_value=True)
    def test_event_id_collision_is_rejected_and_legacy_outcomes_not_invented(self, accept):
        ident = uuid4()
        self.apply(ident)
        with self.assertRaises(ValueError):
            self.apply(ident, account=uuid4())
        accept.return_value = False
        legacy = uuid4()
        self.assertFalse(self.apply(legacy))
        self.assertEqual(QualificationReceipt.objects.get(pk=legacy).status, "legacy")
        self.assertEqual(json.loads(self.read("balance").content)["withheld"], 0)

    def test_empty_balance_is_factual_zero(self):
        data = json.loads(self.read("balance").content)
        self.assertEqual([data[key] for key in ("balance", "confirmed", "pending", "withheld", "reversed")], [0] * 5)
