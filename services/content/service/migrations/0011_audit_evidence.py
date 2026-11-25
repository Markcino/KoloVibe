import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


def install_guard(apps, schema_editor):
    """Append-only at the database: the runtime login cannot change or remove video evidence (D11-007)."""
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION prevent_content_audit_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'content audit events are append-only'; END $$
        """)
        schema_editor.execute("""
            CREATE TRIGGER content_audit_no_mutation BEFORE UPDATE OR DELETE ON content_audit_event
            FOR EACH ROW EXECUTE FUNCTION prevent_content_audit_mutation()
        """)
        schema_editor.execute("""
            CREATE TRIGGER content_audit_no_truncate BEFORE TRUNCATE ON content_audit_event
            FOR EACH STATEMENT EXECUTE FUNCTION prevent_content_audit_mutation()
        """)
    elif schema_editor.connection.vendor == "sqlite":
        for action in ("UPDATE", "DELETE"):
            schema_editor.execute(f"""
                CREATE TRIGGER content_audit_no_{action.lower()} BEFORE {action} ON content_audit_event
                BEGIN SELECT RAISE(ABORT, 'content audit events are append-only'); END
            """)
    else:
        raise RuntimeError("Content audit evidence requires PostgreSQL or fixture SQLite")


def remove_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP FUNCTION IF EXISTS prevent_content_audit_mutation() CASCADE")


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0010_copyright_pipeline"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(max_length=64)),
                ("actor_id", models.UUIDField(null=True)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("subject_type", models.CharField(default="video", max_length=32)),
                ("subject_id", models.UUIDField()),
            ],
            options={"db_table": "content_audit_event"},
        ),
        migrations.CreateModel(
            name="AuditDelivery",
            fields=[
                ("event", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True,
                                               serialize=False, to="service.auditevent")),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("delivered_at", models.DateTimeField(null=True)),
                ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.RunPython(install_guard, reverse_code=remove_guard),
    ]
