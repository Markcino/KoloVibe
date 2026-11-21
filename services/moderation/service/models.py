"""Moderation-owned pilot reports, appeals and attributable decisions."""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Report(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    video_id = models.UUIDField()
    reporter_id = models.UUIDField()
    reason = models.CharField(max_length=16)
    details = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=16, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "id"], name="mod_report_queue_idx")]
        constraints = [
            models.UniqueConstraint(fields=["video_id", "reporter_id"], condition=Q(status="open"),
                                    name="mod_one_open_report_per_viewer"),
        ]


class ModerationAction(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    video_id = models.UUIDField()
    reviewer_id = models.UUIDField()
    action = models.CharField(max_length=16)
    reason = models.TextField(max_length=2000)
    reason_code = models.CharField(max_length=64, null=True)
    creator_id = models.UUIDField(null=True, db_index=True)
    owner_lookup_completed = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(null=True)
    report = models.ForeignKey(Report, null=True, on_delete=models.PROTECT)
    appeal = models.ForeignKey("Appeal", null=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=["video_id", "action", "status", "-revision"], name="mod_video_actions_idx")]
        constraints = [
            models.UniqueConstraint(fields=["video_id"], condition=Q(status="pending"),
                                    name="mod_one_pending_action_per_video"),
        ]


class Appeal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    removal = models.OneToOneField(ModerationAction, on_delete=models.PROTECT, related_name="filed_appeal")
    appellant_id = models.UUIDField()
    reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=16, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "id"], name="mod_appeal_queue_idx")]


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField()
    kind = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(default=timezone.now)
    subject_type = models.CharField(max_length=32)
    subject_id = models.UUIDField()

    class Meta:
        db_table = "moderation_audit_event"


class AuditDelivery(models.Model):
    event = models.OneToOneField(AuditEvent, primary_key=True, on_delete=models.PROTECT)
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)


class ModeratorAssignment(models.Model):
    """Explicit resource grant; routing policy and SLAs remain an owner decision."""
    moderator_id = models.UUIDField()
    queue_scope = models.CharField(max_length=8, choices=[(kind, kind) for kind in ("videos", "reports", "appeals")])
    target_id = models.UUIDField()
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["moderator_id", "queue_scope", "target_id"],
                                               name="mod_unique_assignment"),
                       models.CheckConstraint(condition=Q(queue_scope__in=["videos", "reports", "appeals"]),
                                              name="mod_assignment_scope")]
        indexes = [models.Index(fields=["moderator_id", "queue_scope", "active"], name="mod_assignment_lookup")]
