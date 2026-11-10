from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("service", "0004_moderation_receipt")]

    operations = [
        migrations.AlterField(
            model_name="video", name="moderation_revision",
            field=models.PositiveIntegerField(default=0, db_default=0),
        ),
    ]
