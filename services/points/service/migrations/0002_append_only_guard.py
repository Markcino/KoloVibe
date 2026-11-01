from django.db import migrations


def install_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION prevent_points_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                RAISE EXCEPTION 'points entries are append-only';
            END $$
        """)
        schema_editor.execute("""
            CREATE TRIGGER points_no_update_delete
            BEFORE UPDATE OR DELETE ON points_entries
            FOR EACH ROW EXECUTE FUNCTION prevent_points_mutation()
        """)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER points_no_update BEFORE UPDATE ON points_entries
            BEGIN SELECT RAISE(ABORT, 'points entries are append-only'); END
        """)
        schema_editor.execute("""
            CREATE TRIGGER points_no_delete BEFORE DELETE ON points_entries
            BEGIN SELECT RAISE(ABORT, 'points entries are append-only'); END
        """)
    else:
        raise RuntimeError("Points append-only guard requires PostgreSQL or local SQLite")


class Migration(migrations.Migration):
    dependencies = [("service", "0001_initial")]
    operations = [migrations.RunPython(install_guard, reverse_code=migrations.RunPython.noop)]
