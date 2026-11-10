from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("service", "0001_pilot_moderation")]
    operations = [migrations.RunSQL(
        "CREATE TABLE IF NOT EXISTS internal_request_nonce ("
        "caller text NOT NULL, nonce text NOT NULL, "
        "received_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "PRIMARY KEY (caller, nonce))",
        reverse_sql=migrations.RunSQL.noop,
    )]
