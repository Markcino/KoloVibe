"""Creator-owned profile and pilot eligibility records."""

import uuid

from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.db.models.functions import Lower


class CreatorProfile(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        RESTRICTED = "restricted", "Restricted"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True)
    handle = models.SlugField(max_length=40, unique=True)
    display_name = models.CharField(max_length=80, blank=True, default="")
    location = models.CharField(max_length=80, blank=True, default="")
    bio = models.TextField(max_length=500, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    restricted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=~Q(status="active") | Q(reviewed_at__isnull=False, restricted_at__isnull=True),
            name="creator_active_requires_review"),
            models.UniqueConstraint(Lower("handle"), name="creator_handle_case_insensitive")]


class CreatorApplication(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"

    account_id = models.UUIDField(primary_key=True)
    invited_by = models.UUIDField()
    invited_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INVITED)
    profile = models.OneToOneField(CreatorProfile, null=True, on_delete=models.PROTECT)
    attestation_version = models.CharField(max_length=24, blank=True)
    submitted_at = models.DateTimeField(null=True)
    reviewed_by = models.UUIDField(null=True)
    reviewed_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=["status", "account_id"], name="creator_app_queue_idx")]


class OnboardingEvent(models.Model):
    """Service-owned record of each administrative onboarding change; rows are only ever added.

    Kept as the service's own onboarding history; the platform audit trail is AuditEvent below (D11-007).
    """
    class Action(models.TextChoices):
        INVITED = "invited", "Invited"
        REINVITED = "reinvited", "Re-invited"
        REVOKED = "revoked", "Revoked"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id = models.UUIDField()
    actor_id = models.UUIDField()
    action = models.CharField(max_length=16, choices=Action.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["account_id", "created_at"], name="creator_event_account_idx")]


class CopyrightReviewPolicy(models.Model):
    """Explicit trust grant; invitation/creator eligibility alone never confers trust."""
    creator = models.OneToOneField(CreatorProfile, primary_key=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=False)
    sample_percent = models.PositiveSmallIntegerField(default=100)
    version = models.CharField(max_length=32)
    approved_by = models.UUIDField()
    approved_at = models.DateTimeField()
    reason = models.TextField(max_length=2000)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(sample_percent__lte=100), name="copyright_sample_percent")]


class AuditEvent(models.Model):
    """Immutable evidence of a creator change, written in the deciding transaction and delivered to Audit (FR-015).

    Identifiers and the event kind only: no handle, name, bio or reason text ever enters an event.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=64)
    actor_id = models.UUIDField()
    occurred_at = models.DateTimeField(default=timezone.now)
    subject_type = models.CharField(max_length=32)
    subject_id = models.UUIDField()

    class Meta:
        db_table = "creators_audit_event"


class AuditDelivery(models.Model):
    event = models.OneToOneField(AuditEvent, primary_key=True, on_delete=models.PROTECT)
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)


class CreatorRestriction(models.Model):
    """Decision F (D-8): one enforcement measure on a creator, issued by an administrator.

    Rows are kept as history. Only the lift fields are ever set, once. A measure with no expiry is permanent
    until lifted; an expired measure stops applying on its own, so no scheduler is needed. The private reason
    stays in this service; the creator sees the kind, reason code, policy version and dates.
    """
    class Kind(models.TextChoices):
        WARNING = "warning", "Warning"
        UPLOAD = "upload", "Upload restriction"
        PUBLISHING = "publishing", "Publishing restriction"
        MONETIZATION = "monetization", "Monetization restriction"
        SUSPENSION = "suspension", "Suspension"

    id = models.UUIDField(primary_key=True, editable=False)
    creator = models.ForeignKey(CreatorProfile, on_delete=models.PROTECT, related_name="restrictions")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    reason_code = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=32)
    reason = models.TextField(max_length=2000)
    issued_by = models.UUIDField()
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_by = models.UUIDField(null=True, blank=True)
    lift_reason = models.TextField(max_length=2000, blank=True)

    class Meta:
        indexes = [models.Index(fields=["creator", "lifted_at"], name="creator_restriction_active_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=["warning", "upload", "publishing", "monetization", "suspension"]),
                                   name="creator_restriction_kind"),
            models.CheckConstraint(condition=Q(expires_at__isnull=True) | Q(expires_at__gt=models.F("issued_at")),
                                   name="creator_restriction_expiry_after_issue"),
            models.CheckConstraint(condition=Q(lifted_at__isnull=True, lifted_by__isnull=True)
                                   | Q(lifted_at__isnull=False, lifted_by__isnull=False), name="creator_restriction_lift"),
        ]


class RestrictionAppeal(models.Model):
    """The creator's one appeal against one measure, decided by an administrator who did not issue it."""
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        UPHELD = "upheld", "Upheld"
        LIFTED = "lifted", "Lifted"

    id = models.UUIDField(primary_key=True, editable=False)
    restriction = models.OneToOneField(CreatorRestriction, on_delete=models.PROTECT, related_name="appeal")
    appellant_id = models.UUIDField()
    reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(default=timezone.now)
    decided_by = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(max_length=2000, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "id"], name="creator_appeal_queue_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=["open", "upheld", "lifted"]), name="creator_appeal_status"),
            models.CheckConstraint(condition=Q(status="open", decided_at__isnull=True)
                                   | (~Q(status="open") & Q(decided_at__isnull=False, decided_by__isnull=False)),
                                   name="creator_appeal_decision"),
        ]
