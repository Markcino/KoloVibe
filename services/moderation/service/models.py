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
    copyright = models.BooleanField(default=False, db_default=False)
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


class ReviewerPreview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField()
    queue_scope = models.CharField(max_length=8)
    target_id = models.UUIDField()
    video_id = models.UUIDField()
    expires_at = models.DateTimeField(db_index=True)


class CopyrightNotice(models.Model):
    report = models.OneToOneField(Report, primary_key=True, on_delete=models.PROTECT)
    work_reference = models.CharField(max_length=500)
    version = models.CharField(max_length=32, default="R1-copyright-intake-v1")
    submitted_at = models.DateTimeField(auto_now_add=True)
    # Decision E: whether the claimant was a verified rights holder when the claim arrived, and for whom.
    # Shown to reviewers only, never to the creator.
    claimant_verified = models.BooleanField(default=False, db_default=False)
    organisation = models.CharField(max_length=200, blank=True, default="", db_default="")


class RightsHolder(models.Model):
    """Decision E (D11-008): an account an administrator verified as acting for a rights holder.

    Verification marks a claim for reviewers; it never decides one. The evidence note is administrator-only.
    """
    account_id = models.UUIDField(primary_key=True)
    organisation = models.CharField(max_length=200)
    evidence = models.TextField(max_length=2000)
    verified_by = models.UUIDField()
    verified_at = models.DateTimeField(default=timezone.now)
    revoked_by = models.UUIDField(null=True)
    revoked_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(verified_by=models.F("account_id")), name="mod_rights_holder_not_self"),
            models.CheckConstraint(condition=Q(revoked_by__isnull=True, revoked_at__isnull=True)
                                   | Q(revoked_by__isnull=False, revoked_at__isnull=False),
                                   name="mod_rights_holder_revoke_pair"),
        ]


class CounterNotice(models.Model):
    appeal = models.OneToOneField(Appeal, primary_key=True, on_delete=models.PROTECT)
    request_id = models.UUIDField(unique=True)
    account_id = models.UUIDField()
    version = models.CharField(max_length=32, default="R1-counter-notice-v1")
    submitted_at = models.DateTimeField(auto_now_add=True)


class CopyrightStrike(models.Model):
    removal = models.OneToOneField(ModerationAction, primary_key=True, on_delete=models.PROTECT)
    creator_id = models.UUIDField(db_index=True)
    reversed_by = models.OneToOneField(ModerationAction, null=True, on_delete=models.PROTECT, related_name="reversed_copyright_strike")


class EditDecision(models.Model):
    """Decision A (RV2-01): one reviewer's decision on a held edit to a published video.

    Recorded before Content applies it, so a lost answer is replayed with the same id. A revision gets at most
    one decision that did not conflict.
    """
    id = models.UUIDField(primary_key=True, editable=False)
    revision_id = models.UUIDField()
    video_id = models.UUIDField(db_index=True)
    creator_id = models.UUIDField(db_index=True)
    reviewer_id = models.UUIDField()
    action = models.CharField(max_length=8, choices=[("approve", "approve"), ("reject", "reject")])
    reason = models.TextField(max_length=2000)
    reason_code = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["revision_id"], condition=~Q(status="conflict"),
                                    name="mod_one_decision_per_edit"),
            models.CheckConstraint(condition=Q(action__in=["approve", "reject"]), name="mod_edit_decision_action"),
            models.CheckConstraint(condition=Q(status__in=["pending", "applied", "conflict"]),
                                   name="mod_edit_decision_status"),
        ]
