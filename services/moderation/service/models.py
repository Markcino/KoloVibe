"""Moderation-owned pilot reports, appeals and attributable decisions."""

import uuid

from django.db import models
from django.db.models import Q


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
