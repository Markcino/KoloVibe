"""Decision C slice 2a: Engagement erases one account's engagement data and confirms it."""
import uuid
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from service import privacy
from service.models import CreatorFollow, FraudHold, QualifiedWatch, VideoLike, VideoShare, WatchSession


class EngagementErasureTests(TestCase):
    def setUp(self):
        self.person, self.other = str(uuid.uuid4()), str(uuid.uuid4())
        self.request_id, self.video, self.creator = str(uuid.uuid4()), uuid.uuid4(), uuid.uuid4()
        now = timezone.now()
        for account in (self.person, self.other):
            VideoLike.objects.create(video_id=self.video, account_id=account, creator_id=self.creator)
            CreatorFollow.objects.create(creator_id=self.creator, account_id=account)
            VideoShare.objects.create(account_id=account, video_id=self.video, creator_id=self.creator, day=date.today())
            WatchSession.objects.create(account_id=account, video_id=self.video, creator_user_id=self.creator,
                                        duration_ms=60000, revision=1, started_at=now, last_sample_at=now,
                                        expires_at=now + timedelta(hours=1))
        QualifiedWatch.objects.create(session_id=uuid.uuid4(), account_id=self.person, video_id=self.video,
                                      creator_user_id=self.creator, qualified_at=now, duration_ms=60000)
        self.accepted = self.enterContext(patch("service.privacy.accept_once", return_value=True))
        self.recorded = self.enterContext(patch("service.privacy.record_event"))

    def payload(self, **changes):
        return {"request_id": self.request_id, "account_id": self.person, "service": "engagement"} | changes

    def test_deletes_only_this_account_and_reports_retained_categories(self):
        self.assertTrue(privacy.erase(str(uuid.uuid4()), self.payload()))
        for model in (VideoLike, CreatorFollow, VideoShare, WatchSession):
            self.assertFalse(model.objects.filter(account_id=self.person).exists(), model.__name__)
            self.assertTrue(model.objects.filter(account_id=self.other).exists(), model.__name__)
        self.assertTrue(QualifiedWatch.objects.filter(account_id=self.person).exists(), "retained pending a decision")
        event_type, confirmation = self.recorded.call_args.args
        self.assertEqual(event_type, "privacy.erasure_confirmed")
        self.assertEqual(confirmation, {"request_id": self.request_id, "account_id": self.person, "service": "engagement",
                                        "counts": {"likes": 1, "follows": 1, "shares": 1, "watch_sessions": 1},
                                        "retained": ["qualified_watches"]})

    def test_a_repeat_delivery_changes_nothing(self):
        self.accepted.return_value = False
        self.assertFalse(privacy.erase(str(uuid.uuid4()), self.payload()))
        self.assertTrue(VideoLike.objects.filter(account_id=self.person).exists())
        self.recorded.assert_not_called()

    def test_nothing_left_means_nothing_retained(self):
        QualifiedWatch.objects.all().delete()
        FraudHold.objects.create(account_id=self.other, video_id=self.video, reason_code="X")
        privacy.erase(str(uuid.uuid4()), self.payload())
        self.assertEqual(self.recorded.call_args.args[1]["retained"], [])

    def test_malformed_requests_are_refused_before_any_change(self):
        for bad in (self.payload(service="points"), self.payload(account_id="nope"), self.payload(extra=1),
                    {"request_id": self.request_id}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.erase(str(uuid.uuid4()), bad)
        self.accepted.assert_not_called()
        self.assertEqual(VideoLike.objects.count(), 2)
