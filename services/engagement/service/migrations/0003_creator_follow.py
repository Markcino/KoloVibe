from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("service", "0002_watch_session")]

    operations = [
        migrations.CreateModel(
            name="CreatorFollow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator_id", models.UUIDField()),
                ("account_id", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("creator_id", "account_id"), name="unique_creator_account_follow"),
            ]},
        ),
    ]
