"""Creator-owned profile and pilot eligibility records."""

import uuid

from django.db import models
from django.db.models import Q


class CreatorProfile(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        RESTRICTED = "restricted", "Restricted"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True)
    handle = models.SlugField(max_length=40, unique=True)
    bio = models.TextField(max_length=500, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    restricted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=~Q(status="active") | Q(reviewed_at__isnull=False, restricted_at__isnull=True),
            name="creator_active_requires_review")]


class CreatorApplication(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

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
