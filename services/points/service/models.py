"""Non-cash append-only points ledger. DEC-003 awards arrive through the private event queue."""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class PointsEntry(models.Model):
    class Type(models.TextChoices):
        AWARD = "AWARD", "Award"
        REVERSAL = "REVERSAL", "Reversal"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    entry_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator_user_id = models.UUIDField(db_index=True)
    source_decision_id = models.UUIDField(null=True, blank=True, unique=True)
    delta = models.BigIntegerField()
    entry_type = models.CharField(max_length=16, choices=Type.choices)
    rule_version = models.CharField(max_length=32)
    reversal_of = models.OneToOneField("self", null=True, blank=True,
                                       on_delete=models.PROTECT, related_name="reversal")
    reason_code = models.CharField(max_length=64)
    video_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "points_entries"
        indexes = [models.Index(fields=["creator_user_id", "-created_at"],
                                name="points_creator_created_idx")]
        constraints = [models.CheckConstraint(
            condition=(
                Q(entry_type="AWARD", delta__gt=0, source_decision_id__isnull=False,
                  reversal_of__isnull=True)
                | Q(entry_type="REVERSAL", delta__lt=0, reversal_of__isnull=False)
                | Q(entry_type="ADJUSTMENT", reversal_of__isnull=True)
            ) & ~Q(delta=0), name="points_valid_entry")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Points entries are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Points entries are append-only")


class DailyAwardCount(models.Model):
    creator_user_id = models.UUIDField()
    day = models.DateField()
    awards = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["creator_user_id", "day"], name="points_creator_day_unique"),
            models.CheckConstraint(condition=Q(awards__lte=100), name="points_daily_awards_lte_100"),
        ]


class QualificationReceipt(models.Model):
    """Durable received events; terminal outcomes never fabricate ledger entries."""
    id = models.UUIDField(primary_key=True)
    creator_user_id = models.UUIDField(db_index=True)
    qualified_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=16, default="pending", choices=[
        (value, value) for value in ("pending", "posted", "withheld", "legacy")])
    amount = models.PositiveSmallIntegerField(default=1)
    reason_code = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [models.Index(fields=["creator_user_id", "status", "-received_at"],
                                name="points_receipt_owner_state")]
        constraints = [models.CheckConstraint(condition=Q(amount=1), name="points_receipt_one_point")]


class AuditEvent(models.Model):
    """Immutable evidence of a ledger decision, written in the deciding transaction.

    The actor is null: awards and cap withholdings are server decisions, not user
    actions. The subject is the qualification event id, which is also the ledger
    entry id for posted awards.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=64)
    actor_id = models.UUIDField(null=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    subject_type = models.CharField(max_length=32, default="points_entry")
    subject_id = models.UUIDField()

    class Meta:
        db_table = "points_audit_event"


class AuditDelivery(models.Model):
    event = models.OneToOneField(AuditEvent, primary_key=True, on_delete=models.PROTECT)
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)
