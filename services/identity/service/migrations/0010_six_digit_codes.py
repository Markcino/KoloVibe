"""ADR-013 amendment A-1: six-digit email codes with per-code attempt counters.

Expand step only. Existing pending rows become ``kind='token'`` so long links already
emailed keep working until they expire (verification: at most 24 hours; reset: at most
30 minutes). Rows created after this migration default to ``kind='code'``.
"""

import uuid

import django.utils.timezone
from django.db import migrations, models

KIND_CHOICES = [("token", "Legacy long token"), ("code", "Six-digit code")]


def _fields(model):
    return [
        migrations.AddField(model, "kind", models.CharField(
            max_length=5, choices=KIND_CHOICES, default="token")),
        migrations.AddField(model, "issue_id", models.UUIDField(default=uuid.uuid4, editable=False)),
        migrations.AddField(model, "attempts", models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model, "created_at", models.DateTimeField(
            default=django.utils.timezone.now)),
        # Existing rows keep "token"; every new row is a six-digit code.
        migrations.AlterField(model, "kind", models.CharField(
            max_length=5, choices=KIND_CHOICES, default="code")),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0009_reauthentication_open_privacy_requests"),
    ]

    operations = _fields("emailverification") + _fields("passwordreset")
