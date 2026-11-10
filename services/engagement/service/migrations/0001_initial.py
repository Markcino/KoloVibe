from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="VideoLike",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("video_id", models.UUIDField()),
                ("account_id", models.UUIDField()),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("video_id", "account_id"), name="unique_video_account_like"),
                ],
            },
        ),
        migrations.RunSQL(
            "CREATE TABLE IF NOT EXISTS internal_request_nonce ("
            "caller text NOT NULL, nonce text NOT NULL, "
            "received_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (caller, nonce))",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
