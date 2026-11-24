"""Creator-owned profile and pilot eligibility records."""

import uuid

from django.db import models
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

    Creators has no Audit delivery credential, so this is the durable who/what/when until one is provisioned.
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
