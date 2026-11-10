import uuid

from django.db import models


class VideoLike(models.Model):
    video_id = models.UUIDField()
    account_id = models.UUIDField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["video_id", "account_id"], name="unique_video_account_like"),
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
        constraints = [
            models.UniqueConstraint(fields=["account_id", "video_id"], name="watch_account_video_unique"),
        ]
