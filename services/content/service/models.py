"""Content-owned video metadata. Media bytes stay with the approved provider."""

import uuid

from django.db import models
from django.db.models import Q


class Video(models.Model):
    class Category(models.TextChoices):
        HIPCO = "hipco", "Hipco"
        AFROBEATS = "afrobeats", "Afrobeats"
        COMEDY = "comedy", "Comedy"
        SKITS = "skits", "Skits"
        SHORT_FILMS = "short_films", "Short films"
        CULTURE = "culture", "Culture"
        DOCUMENTARIES = "documentaries", "Documentaries"

    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        UPLOADING = "uploading", "Uploading"
        PROCESSING = "processing", "Processing"
        FAILED = "failed", "Processing failed"
        REVIEW = "review", "Review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        REMOVED = "removed", "Removed"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PUBLIC = "public", "Public"
        UNLISTED = "unlisted", "Unlisted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator_id = models.UUIDField()
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, max_length=2000)
    category = models.CharField(max_length=16, choices=Category.choices, null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    cover_time_ms = models.PositiveIntegerField(null=True, blank=True)
    poster_asset_id = models.CharField(max_length=255, null=True, blank=True)
    failure_reason = models.CharField(max_length=32, null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PRIVATE)
    provider_asset_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    moderation_revision = models.PositiveIntegerField(default=0, db_default=0)
    moderation_approved_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["-created_at", "-id"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(cover_time_ms__isnull=True) | Q(duration_ms__isnull=True)
                | Q(cover_time_ms__lte=models.F("duration_ms")), name="cover_within_video_duration"),
            models.CheckConstraint(
                condition=(
                    ~Q(state="published")
                    | (
                        Q(moderation_approved_at__isnull=False)
                        & Q(provider_asset_id__isnull=False)
                        & ~Q(provider_asset_id="")
                    )
                ),
                name="published_requires_approved_provider_asset",
            ),
        ]


class ModerationReceipt(models.Model):
    action_id = models.UUIDField(primary_key=True)
    video_id = models.UUIDField()
    action = models.CharField(max_length=16)
    previous_revision = models.PositiveIntegerField()


class MediaUpload(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name="media_upload")
    expected_bytes = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    source_etag = models.CharField(max_length=128, blank=True)
    lease_id = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)

    @property
    def source_key(self):
        return f"originals/{self.id}.mp4"
