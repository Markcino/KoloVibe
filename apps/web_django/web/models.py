"""Private browser credentials; the browser cookie carries only a session ID."""

from django.db import models


class WebCredential(models.Model):
    session_key = models.CharField(max_length=40, primary_key=True)
    identity_session_id = models.UUIDField()
    ciphertext = models.BinaryField()
    created_at = models.DateTimeField()
    last_activity_at = models.DateTimeField()
    absolute_expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "web_credential"
