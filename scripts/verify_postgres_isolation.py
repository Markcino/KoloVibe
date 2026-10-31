"""Execute as each PostgreSQL service login to verify least-privilege schema access."""
import os
from pathlib import Path
SERVICES = ("gateway","identity","creators","content","engagement","points","moderation","audit")
service = os.environ["KOLOVIBE_SERVICE_NAME"]
if service not in SERVICES:
    raise SystemExit("Unknown service")
import psycopg
with psycopg.connect(
    dbname=os.environ["KOLOVIBE_DB_NAME"],
    user=os.environ["KOLOVIBE_DB_USER"],
    password=Path(os.environ["KOLOVIBE_DB_PASSWORD_FILE"]).read_text().strip(),
    host=os.environ["KOLOVIBE_DB_HOST"],
    sslrootcert=os.environ["KOLOVIBE_DB_SSLROOTCERT"],
    sslmode="verify-full",
) as db:
    with db.cursor() as cur:
        cur.execute("SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user")
        assert cur.fetchone() == (False,False,False), "Service principal has administrative privileges"
        for schema in SERVICES:
            cur.execute("SELECT has_schema_privilege(current_user,%s,'USAGE'),has_schema_privilege(current_user,%s,'CREATE')",(schema,schema))
            assert cur.fetchone() == ((True,True) if schema==service else (False,False)), f"Isolation failed: {schema}"
print(f"PASS: {service} schema is isolated")
