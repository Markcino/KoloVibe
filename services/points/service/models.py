"""Non-cash append-only points ledger. No award API exists until rules approval."""

import uuid

from django.db import models
from django.db.models import Q


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
