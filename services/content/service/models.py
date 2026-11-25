"""Content-owned video metadata. Media bytes stay with the approved provider."""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Video(models.Model):
    class RightsStatus(models.TextChoices):
        ATTESTED = "attested", "Attested"
        FLAGGED = "flagged", "Flagged"
        CLAIMED = "claimed", "Claimed"
        REMOVED = "removed", "Removed"
        RESTORED = "restored", "Restored"

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
    # Legacy records have no per-upload attestation; never invent one in a backfill.
    rights_status = models.CharField(max_length=16, choices=RightsStatus.choices, default=RightsStatus.FLAGGED, db_default=RightsStatus.FLAGGED)
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
    approval_source = models.CharField(max_length=16, default="human", db_default="human")
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["-created_at", "-id"])]
        constraints = [
            models.CheckConstraint(condition=Q(rights_status__in=["attested", "flagged", "claimed", "removed", "restored"]), name="video_rights_state"),
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


class MetadataRevision(models.Model):
    """Decision A (RV2-01): a proposed edit to a published video's text, held until a reviewer decides.

    The approved values on the video stay live while a revision is pending. A newer edit supersedes the pending one,
    so repeated edits never skip review, and rows are kept as history: only the status moves forward.
    """
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Superseded by a newer edit"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.PROTECT, related_name="metadata_revisions")
    proposed = models.JSONField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_id = models.UUIDField(null=True, blank=True, unique=True)
    reason_code = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "id"], name="content_revision_queue_idx"),
                   models.Index(fields=["video", "-created_at"], name="content_revision_video_idx")]
        constraints = [
            models.UniqueConstraint(fields=["video"], condition=Q(status="pending"), name="content_one_pending_revision"),
            models.CheckConstraint(condition=Q(status__in=["pending", "approved", "rejected", "superseded", "withdrawn"]),
                                   name="content_revision_status"),
            models.CheckConstraint(condition=Q(status="pending", decided_at__isnull=True)
                                   | (~Q(status="pending") & Q(decided_at__isnull=False)),
                                   name="content_revision_decided_at"),
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


class OriginalityAttestation(models.Model):
    upload_id = models.UUIDField(primary_key=True)
    video = models.ForeignKey(Video, on_delete=models.PROTECT)
    account_id = models.UUIDField()
    version = models.CharField(max_length=32)
    accepted_at = models.DateTimeField(default=timezone.now)
    review_policy = models.JSONField(default=dict)


class SourceDigest(models.Model):
    sha256 = models.CharField(max_length=64, primary_key=True)
    first_video_id = models.UUIDField()


class PrescreenResult(models.Model):
    upload_id = models.UUIDField(primary_key=True)
    video = models.ForeignKey(Video, on_delete=models.PROTECT)
    source_sha256 = models.CharField(max_length=64)
    fingerprint_sha256 = models.CharField(max_length=64, blank=True)
    reasons = models.JSONField(default=list)
    disposition = models.CharField(max_length=24)
    created_at = models.DateTimeField(auto_now_add=True)


class CopyrightClaimState(models.Model):
    report_id = models.UUIDField(primary_key=True)
    video = models.ForeignKey(Video, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)


class RightsEvent(models.Model):
    """Append-only local evidence; reasons stay private and never enter audit read projections."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_id = models.UUIDField()
    actor_id = models.UUIDField(null=True)
    event = models.CharField(max_length=32)
    reason = models.TextField(max_length=2000)
    occurred_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict)


class Fingerprint(models.Model):
    """Perceptual/audio fingerprints used for duplicate checks; `blocked` entries come from confirmed takedowns."""
    class Kind(models.TextChoices):
        SHA256 = "sha256", "Exact file hash"
        PDQ = "pdq", "PDQ frame hash"
        CHROMAPRINT = "chromaprint", "Chromaprint audio fingerprint"

    video = models.ForeignKey(Video, null=True, blank=True, on_delete=models.CASCADE, related_name="fingerprints")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    value = models.TextField()
    blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["kind", "blocked"], name="fingerprint_kind_blocked_idx"),
                   models.Index(fields=["kind", "value"], name="fingerprint_kind_value_idx", condition=Q(kind="sha256"))]


class ScreeningRecord(models.Model):
    """Append-only audit of each automated screening finding and decision. Never stores media or raw payloads."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="screening_records")
    provider = models.CharField(max_length=32)
    kind = models.CharField(max_length=16)
    score = models.FloatField()
    action = models.CharField(max_length=16, blank=True)
    reason = models.CharField(max_length=64)
    segments = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["video", "created_at"], name="screening_video_time_idx")]


class AuditEvent(models.Model):
    """Immutable evidence of a video change, written in the deciding transaction and delivered to Audit (FR-015).

    Identifiers and the kind only: no title, description, tag, reason or storage key enters an event. The actor is
    null when Content does not know the account (the creator profile owns the video; the worker acts on its own).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=64)
    actor_id = models.UUIDField(null=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    subject_type = models.CharField(max_length=32, default="video")
    subject_id = models.UUIDField()

    class Meta:
        db_table = "content_audit_event"


class AuditDelivery(models.Model):
    event = models.OneToOneField(AuditEvent, primary_key=True, on_delete=models.PROTECT)
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)
