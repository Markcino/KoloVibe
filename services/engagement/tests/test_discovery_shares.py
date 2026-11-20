from datetime import UTC, datetime, timedelta, timezone as datetime_timezone
import json
from unittest.mock import patch
from uuid import UUID, uuid4

from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from service.analytics import creator_engagement, video_engagement
from service.discovery import discovery
from service.follows import follow_api
from service.likes import update_like
from service.models import CreatorFollow, QualifiedWatch, VideoLike, VideoShare
from service.shares import record_share


class DiscoveryShareAnalyticsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.now = datetime(2026, 11, 11, 12, tzinfo=UTC)
        self.enterContext(patch("django.utils.timezone.now", return_value=self.now))
        self.creator, self.owner, self.viewer, self.video = (uuid4() for _ in range(4))

    def request(self, data, caller="gateway"):
        request = self.factory.post("/internal/test", data, content_type="application/json")
        request.service_caller = caller
        return request

    def qualify(self, video=None, at=None, watched=2000, owner=None):
        return QualifiedWatch.objects.create(session_id=uuid4(), account_id=uuid4(), video_id=video or self.video,
            creator_user_id=owner or self.owner, qualified_at=at or self.now, duration_ms=5000, watched_ms=watched)

    def summary(self, period="7d", **fields):
        return creator_engagement(self.request({"creator_id": str(self.creator), "creator_user_id": str(self.owner),
                                                "range": period, **fields}))

    def test_signed_counts_return_real_zeros_and_reject_more_than_fifty_ids(self):
        other = uuid4()
        VideoLike.objects.create(video_id=self.video, account_id=self.viewer)
        response = discovery(self.request({"video_ids": [str(self.video), str(other)]}), "like-counts")
        self.assertEqual(json.loads(response.content), {"counts": {str(self.video): 1, str(other): 0}})
        self.assertEqual(discovery(self.request({"video_ids": [str(other)] * 51}), "like-counts").status_code, 400)
        self.assertEqual(discovery(self.request({"video_ids": [str(other)]}, "content"), "like-counts").status_code, 403)
        self.assertEqual(discovery(self.request({"video_ids": [True]}), "like-counts").status_code, 400)
        CreatorFollow.objects.create(creator_id=self.creator, account_id=self.viewer)
        response = discovery(self.request({"creator_id": str(self.creator)}), "follower-count")
        self.assertEqual(json.loads(response.content), {"creator_id": str(self.creator), "follower_count": 1})
        response = self.client.post("/internal/engagement/like-counts", {"video_ids": []}, content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_play_counts_are_the_all_time_qualified_aggregate_and_expose_nothing_else(self):
        other, empty = uuid4(), uuid4()
        for _ in range(3):
            self.qualify(video=self.video)
        self.qualify(video=self.video, at=self.now - timedelta(days=400))  # old plays still count
        self.qualify(video=other)
        WatchCount = QualifiedWatch.objects.filter(video_id=self.video).count()
        self.assertEqual(WatchCount, 4)
        response = discovery(self.request({"video_ids": [str(self.video), str(other), str(empty), str(other)]}),
                             "play-counts")
        self.assertEqual(json.loads(response.content),
                         {"counts": {str(self.video): 4, str(other): 1, str(empty): 0}})
        self.assertEqual(set(json.loads(response.content)), {"counts"})
        self.assertEqual(discovery(self.request({"video_ids": []}), "play-counts").status_code, 200)

    def test_play_counts_reject_bad_input_other_callers_and_extra_fields(self):
        for body in ({"video_ids": [str(uuid4())] * 51}, {"video_ids": [True]}, {"video_ids": ["x"]},
                     {"video_ids": "id"}, {}, {"video_ids": [], "viewer_id": str(uuid4())},
                     {"video_ids": [], "creator_id": str(self.creator)}):
            self.assertEqual(discovery(self.request(body), "play-counts").status_code, 400, body)
        for caller in ("content", "creators", "", None):
            self.assertEqual(discovery(self.request({"video_ids": []}, caller), "play-counts").status_code, 403)
        response = self.client.post("/internal/engagement/play-counts", {"video_ids": []},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_trending_uses_seven_day_qualified_records_and_deterministic_cursor_ties(self):
        first, second, third = (UUID(int=value) for value in (1, 2, 3))
        for video in (first, first, second, second, third):
            self.qualify(video=video)
        self.qualify(video=third, at=self.now - timedelta(days=7, milliseconds=1))
        self.qualify(video=third, at=self.now + timedelta(seconds=1))
        result = discovery(self.request({"limit": 2, "cursor": None}), "trending")
        page = json.loads(result.content)
        self.assertEqual(page["items"], [{"video_id": str(first), "qualified_plays": 2}, {"video_id": str(second), "qualified_plays": 2}])
        second_page = json.loads(discovery(self.request({"limit": 2, "cursor": page["next_cursor"]}), "trending").content)
        self.assertEqual(second_page, {"items": [{"video_id": str(third), "qualified_plays": 1}], "next_cursor": None})
        self.assertEqual(discovery(self.request({"limit": 2, "cursor": page["next_cursor"] + "tampered"}), "trending").status_code, 400)

    def test_share_deduplicates_account_video_utc_day_and_emits_no_points(self):
        data = {"account_id": str(self.viewer), "video_id": str(self.video), "creator_id": str(self.creator)}
        with patch("service.events.record_event") as events:
            first = record_share(self.request(data)); second = record_share(self.request(data))
            self.assertEqual((first.status_code, first.content), (second.status_code, second.content))
            self.assertEqual(VideoShare.objects.count(), 1)
            self.assertEqual(VideoShare.objects.get().day, self.now.date())
            record_share(self.request(data | {"account_id": str(uuid4())}))
            self.assertEqual(VideoShare.objects.count(), 2)
            with patch("django.utils.timezone.now", return_value=self.now + timedelta(days=1)):
                record_share(self.request(data))
            self.assertEqual(VideoShare.objects.count(), 3)
            events.assert_not_called()
        self.assertFalse(QualifiedWatch.objects.exists())
        self.assertEqual(record_share(self.request(data | {"day": "2020-01-01"})).status_code, 400)
        self.assertEqual(record_share(self.request(data, "identity")).status_code, 403)
        with self.assertRaises(IntegrityError), transaction.atomic():
            VideoShare.objects.create(account_id=self.viewer, video_id=self.video, creator_id=self.creator, day=self.now.date())

    def test_share_day_is_utc_even_when_clock_carries_another_offset(self):
        local = datetime(2026, 11, 12, 0, 30, tzinfo=datetime_timezone(timedelta(hours=2)))
        with patch("django.utils.timezone.now", return_value=local):
            record_share(self.request({"account_id": str(self.viewer), "video_id": str(self.video), "creator_id": str(self.creator)}))
        self.assertEqual(VideoShare.objects.get().day.isoformat(), "2026-11-11")

    def test_range_summary_counts_only_owned_observed_records_and_builds_daily_top_five(self):
        for index in range(6):
            video = UUID(int=index + 1)
            self.qualify(video=video, at=self.now - timedelta(days=1), watched=2500)
        self.qualify(at=self.now - timedelta(days=10), watched=3000)
        self.qualify(owner=uuid4())
        VideoLike.objects.create(video_id=self.video, account_id=self.viewer, creator_id=self.creator, created_at=self.now)
        VideoLike.objects.create(video_id=uuid4(), account_id=uuid4(), creator_id=self.creator, created_at=None)
        VideoLike.objects.create(video_id=uuid4(), account_id=uuid4(), creator_id=uuid4(), created_at=self.now)
        CreatorFollow.objects.create(creator_id=self.creator, account_id=self.viewer)
        CreatorFollow.objects.filter(creator_id=self.creator).update(created_at=self.now)
        VideoShare.objects.create(account_id=self.viewer, video_id=self.video, creator_id=self.creator, day=self.now.date(), created_at=self.now)
        result = json.loads(self.summary().content)
        self.assertEqual({key: result[key] for key in ("range", "qualified_plays", "watch_time_seconds", "likes", "new_followers", "shares")},
                         {"range": "7d", "qualified_plays": 6, "watch_time_seconds": 15.0, "likes": 1, "new_followers": 1, "shares": 1})
        self.assertEqual(len(result["daily"]), 7)
        self.assertEqual(sum(row["qualified_plays"] for row in result["daily"]), 6)
        self.assertEqual([row["video_id"] for row in result["top_videos"]], [str(UUID(int=i)) for i in range(1, 6)])
        self.assertEqual(json.loads(self.summary("28d").content)["qualified_plays"], 7)

    def test_empty_ranges_return_zeros_and_empty_series_without_demo_data(self):
        result = json.loads(self.summary().content)
        self.assertEqual((result["qualified_plays"], result["watch_time_seconds"], result["likes"], result["new_followers"], result["shares"]), (0, 0, 0, 0, 0))
        self.assertEqual((result["daily"], result["top_videos"]), ([], []))
        self.assertEqual(self.summary("90d").status_code, 400)
        self.assertEqual(self.summary(account_id=str(uuid4())).status_code, 400)

    def test_video_since_published_keeps_existing_counts_and_uses_sampled_watch_time(self):
        self.qualify(at=self.now - timedelta(days=2), watched=2500)
        self.qualify(at=self.now - timedelta(days=20), watched=None)
        VideoLike.objects.create(video_id=self.video, account_id=self.viewer, created_at=self.now)
        VideoShare.objects.create(account_id=self.viewer, video_id=self.video, creator_id=self.creator, day=self.now.date(), created_at=self.now)
        result = video_engagement(self.request({"video_id": str(self.video), "range": "since_published", "published_at": (self.now-timedelta(days=30)).isoformat()}))
        data = json.loads(result.content)
        self.assertEqual((data["current_likes"], data["qualified_viewers"]), (1, 0))
        self.assertEqual((data["qualified_plays"], data["watch_time_seconds"], data["likes"], data["shares"], data["average_watch_seconds"]), (2, 2.5, 1, 1, 1.25))
        seven = json.loads(video_engagement(self.request({"video_id": str(self.video), "range": "7d", "published_at": None})).content)
        self.assertEqual((seven["qualified_plays"], seven["average_watch_seconds"]), (1, 2.5))

    def test_like_follow_responses_have_real_counts_and_repeat_without_timestamp_changes(self):
        data = {"account_id": str(self.viewer), "video_id": str(self.video), "creator_id": str(self.creator), "liked": True}
        first = update_like(self.request(data)); created_at = VideoLike.objects.get().created_at
        second = update_like(self.request(data))
        self.assertEqual(first.content, second.content)
        self.assertEqual(json.loads(first.content)["like_count"], 1)
        self.assertEqual(VideoLike.objects.get().created_at, created_at)
        for _ in range(2):
            response = update_like(self.request(data | {"liked": False}))
            self.assertEqual(json.loads(response.content), {"video_id": str(self.video), "liked": False, "like_count": 0})
        follow = {"account_id": str(self.viewer), "creator_id": str(self.creator), "operation": "follow"}
        first = follow_api(self.request(follow)); second = follow_api(self.request(follow))
        self.assertEqual(first.content, second.content)
        for _ in range(2):
            response = follow_api(self.request(follow | {"operation": "unfollow"}))
            self.assertEqual(json.loads(response.content), {"creator_id": str(self.creator), "following": False, "follower_count": 0})
