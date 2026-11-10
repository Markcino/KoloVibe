from django.db import models


class VideoLike(models.Model):
    video_id = models.UUIDField()
    account_id = models.UUIDField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["video_id", "account_id"], name="unique_video_account_like"),
        ]
