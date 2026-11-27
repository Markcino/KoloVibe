from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0016_erasure_creator_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="privacyrequest",
            name="completed_under_policy",
            field=models.CharField(blank=True, db_default="", editable=False, max_length=64),
        ),
    ]
