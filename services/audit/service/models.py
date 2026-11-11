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
