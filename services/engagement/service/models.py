import uuid

from django.db import models
from django.utils import timezone


class VideoLike(models.Model):
    video_id = models.UUIDField()
    account_id = models.UUIDField()
    creator_id = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["video_id", "account_id"], name="unique_video_account_like"),
        ]


class CreatorFollow(models.Model):
    creator_id = models.UUIDField()
    account_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["creator_id", "account_id"], name="unique_creator_account_follow"),
        ]


class WatchSession(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    account_id = models.UUIDField()
    video_id = models.UUIDField()
    creator_user_id = models.UUIDField()
    duration_ms = models.PositiveIntegerField()
    revision = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    last_sample_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    position_ms = models.PositiveIntegerField(default=0)
    qualified_at = models.DateTimeField(null=True)
    invalidated = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["video_id", "qualified_at"], name="eng_watch_video_qual_idx")]
        constraints = [
            models.UniqueConstraint(fields=["account_id", "video_id"], name="watch_account_video_unique"),
        ]


class QualifiedWatch(models.Model):
    """A server-qualified play retained when the renewable session is replaced.

    Qualification identity/time never changes. Only validated progress from the
    same session may increase watched_ms; null represents unknown legacy time.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.UUIDField(db_index=True)
    account_id = models.UUIDField()
    video_id = models.UUIDField()
    creator_user_id = models.UUIDField()
    qualified_at = models.DateTimeField()
    duration_ms = models.PositiveIntegerField()
    watched_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account_id", "video_id", "qualified_at"], name="qualified_watch_once"),
            models.CheckConstraint(condition=models.Q(watched_ms__isnull=True)
                                   | models.Q(watched_ms__lte=models.F("duration_ms")), name="qualified_time_within_duration"),
        ]
        indexes = [models.Index(fields=["qualified_at", "video_id"], name="eng_qualified_range_idx"),
                   models.Index(fields=["video_id", "qualified_at"], name="eng_qualified_video_idx"),
                   models.Index(fields=["creator_user_id", "qualified_at"], name="eng_qualified_creator_idx")]


class VideoShare(models.Model):
    """One share intent per account/video/UTC day; no reward is emitted."""

    account_id = models.UUIDField()
    video_id = models.UUIDField()
    creator_id = models.UUIDField(db_index=True)
    day = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account_id", "video_id", "day"], name="unique_daily_video_share")]
        indexes = [models.Index(fields=["creator_id", "day"], name="eng_share_creator_day_idx")]


class FraudHold(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id = models.UUIDField()
    video_id = models.UUIDField(db_index=True)
    reason_code = models.CharField(max_length=64)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["active", "video_id", "id"], name="eng_active_hold_scope")]
