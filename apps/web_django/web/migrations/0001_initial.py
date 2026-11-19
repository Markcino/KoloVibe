from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(
        name="WebCredential",
        fields=[
            ("session_key", models.CharField(max_length=40, primary_key=True, serialize=False)),
            ("identity_session_id", models.UUIDField()),
            ("ciphertext", models.BinaryField()),
            ("created_at", models.DateTimeField()),
            ("last_activity_at", models.DateTimeField()),
            ("absolute_expires_at", models.DateTimeField(db_index=True)),
        ],
        options={"db_table": "web_credential"},
    )]
