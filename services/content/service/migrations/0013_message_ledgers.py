from django.db import migrations


def message_ledgers_for_sqlite(apps, schema_editor):
    """PostgreSQL gets event_outbox and event_inbox from infra/postgres/schema_isolation.sql (owned by the schema
    owner role). Only the SQLite test fixture creates them here, with the same columns (Decision C erasure)."""
    if schema_editor.connection.vendor != "sqlite":
        return
    schema_editor.execute("CREATE TABLE IF NOT EXISTS event_outbox (id char(36) PRIMARY KEY, event_type text NOT NULL, "
                          "payload text NOT NULL, created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                          "published_at datetime, attempts integer NOT NULL DEFAULT 0)")
    schema_editor.execute("CREATE TABLE IF NOT EXISTS event_inbox (id char(36) PRIMARY KEY, event_type text NOT NULL, "
                          "received_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP)")


class Migration(migrations.Migration):
    dependencies = [("service", "0012_published_edit_review")]
    operations = [migrations.RunPython(message_ledgers_for_sqlite, migrations.RunPython.noop)]
