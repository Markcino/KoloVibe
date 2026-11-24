"""Business-owned data. Cross-service identifiers are plain UUID columns with no foreign keys (DOC-204)."""
import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Business(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        NEEDS_INFO = "needs_info", "Needs information"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"
        REVOKED = "revoked", "Revoked"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    display_name = models.CharField(max_length=80)
    legal_name = models.CharField(max_length=160)  # private: owner and assigned reviewers only
    created_by_account_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=["created_by_account_id", "created_at"], name="biz_by_creator_idx")]


class BusinessMembership(models.Model):
    """Authority is a per-business relationship, never an Identity role (ADR-BIZ-001 decision 2)."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="memberships")
    account_id = models.UUIDField()
    role = models.CharField(max_length=8, choices=Role.choices)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    granted_by_account_id = models.UUIDField()
    label = models.CharField(max_length=40, blank=True, default="")  # owner-assigned; no account profile data is copied
    created_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "account_id"], condition=Q(status="active"),
                                    name="biz_one_active_membership"),
            models.CheckConstraint(condition=Q(role__in=["owner", "staff"]), name="biz_membership_role"),
            models.CheckConstraint(condition=Q(status__in=["active", "revoked"]), name="biz_membership_status"),
        ]
        indexes = [models.Index(fields=["account_id", "status"], name="biz_member_by_account_idx")]


class StaffInvitation(models.Model):
    """Single-use, expiring code shared by the owner out of band (DR-BZ-08 option A). Only a keyed digest is stored."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="invitations")
    code_digest = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=40)
    created_by_account_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    redeemed_by_account_id = models.UUIDField(null=True, blank=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class RegistrationGrant(models.Model):
    """Pilot-cohort invitation to register businesses (DR-BZ-03); administrator-managed."""
    account_id = models.UUIDField(primary_key=True)
    granted_by_account_id = models.UUIDField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)


class IdempotencyRecord(models.Model):
    """Replays the recorded result for a repeated key and payload; a different payload conflicts."""
    id = models.BigAutoField(primary_key=True)
    actor_id = models.UUIDField()
    operation = models.CharField(max_length=40)
    key_digest = models.CharField(max_length=64)
    payload_digest = models.CharField(max_length=64)
    status = models.PositiveSmallIntegerField()
    body = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor_id", "operation", "key_digest"],
                                               name="biz_idempotency_unique")]


class ThrottleCounter(models.Model):
    """Hashed key and a window; raw account or address values are never stored."""
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField()


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField()
    kind = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(default=timezone.now)
    subject_type = models.CharField(max_length=32)
    subject_id = models.UUIDField()

    class Meta:
        db_table = "business_audit_event"


class AuditDelivery(models.Model):
    event = models.OneToOneField(AuditEvent, primary_key=True, on_delete=models.PROTECT)
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)
