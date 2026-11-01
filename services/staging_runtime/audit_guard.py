"""Database-level append-only guard for service-owned security evidence."""

def install_guard(apps, schema_editor):
    table = schema_editor.quote_name("service_securityevent")
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION prevent_security_event_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                RAISE EXCEPTION 'security events are append-only';
            END $$
        """)
        schema_editor.execute(f"""
            CREATE TRIGGER security_event_no_mutation BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION prevent_security_event_mutation()
        """)
        schema_editor.execute(f"""
            CREATE TRIGGER security_event_no_truncate BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION prevent_security_event_mutation()
        """)
    elif vendor == "sqlite":
        for action in ("UPDATE", "DELETE"):
            schema_editor.execute(f"""
                CREATE TRIGGER security_event_no_{action.lower()} BEFORE {action} ON {table}
                BEGIN SELECT RAISE(ABORT, 'security events are append-only'); END
            """)
    else:
        raise RuntimeError("Security evidence requires PostgreSQL or fixture SQLite")
