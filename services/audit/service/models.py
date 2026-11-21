import uuid
from django.db import models


class SecurityEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField(null=True)
    kind = models.CharField(max_length=64)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    payload_digest = models.CharField(max_length=64)
    producer = models.CharField(max_length=32, default="identity")
    subject_type = models.CharField(max_length=32, null=True)
    subject_id = models.UUIDField(null=True)

    class Meta:
        indexes = [models.Index(fields=["actor_id", "-occurred_at", "-id"], name="audit_actor_read_idx"),
                   models.Index(fields=["producer", "-occurred_at", "-id"], name="audit_producer_read_idx")]


class AuditReadGrant(models.Model):
    administrator_id = models.UUIDField()
    producer = models.CharField(max_length=32, choices=[(name, name) for name in ("identity", "moderation", "creators", "content", "points", "audit")])
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["administrator_id", "producer"], name="audit_read_grant_unique"),
                       models.CheckConstraint(condition=models.Q(producer__in=["identity", "moderation", "creators", "content", "points", "audit"]), name="audit_read_grant_producer")]
