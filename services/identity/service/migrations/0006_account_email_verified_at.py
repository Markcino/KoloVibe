from django.db import migrations, models


def backfill_verified_email(apps, schema_editor):
    Account = apps.get_model("service", "Account")
    EmailVerification = apps.get_model("service", "EmailVerification")
    alias = schema_editor.connection.alias
    verified = EmailVerification.objects.using(alias).filter(used_at__isnull=False)
    latest = verified.filter(account_id=models.OuterRef("pk")).order_by("-used_at")
    Account.objects.using(alias).filter(pk__in=verified.values("account_id")).update(
        email_verified_at=models.Subquery(latest.values("used_at")[:1]),
    )


class Migration(migrations.Migration):
    dependencies = [("service", "0005_security_event_guard")]

    operations = [
        migrations.AddField(
            model_name="account", name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_verified_email, migrations.RunPython.noop),
    ]
