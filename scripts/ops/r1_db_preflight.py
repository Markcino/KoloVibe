"""Read-only PostgreSQL pre-migration checks for the R1 staging release (no writes, no DDL, no locks beyond reads).

What it answers before any migration is approved:
  * which migrations each service schema already has applied, and which are pending for this release commit;
  * whether the database is *ahead* of the code (an applied migration this commit does not have);
  * whether creators 0004 (case-insensitive unique handle) would fail on existing handles that differ only by case;
  * whether content's `stream_upload_id` column (added by 0003, dropped by 0005) holds any data;
  * which schemas and roles exist, and the server version.

It runs one `READ ONLY` transaction (`SET TRANSACTION READ ONLY`, a statement timeout, SELECT only) over a TLS
`verify-full` connection, so a bug here cannot change data. The password comes from an owner-only file and is never
printed. Output is names and counts only; creator handles are printed only with --show-handles, to the operator's own
terminal, for the manual collision review. Nothing is renamed or repaired by this tool.

Usage (a read-only login or the DBA login, from a host that can reach the database over TLS):
  python3 r1_db_preflight.py --host H --dbname kolovibe_staging --user U --password-file F --sslrootcert CA
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ("identity", "creators", "content", "engagement", "points", "moderation", "audit", "gateway")
STATEMENT_TIMEOUT_MS = 5000
MIGRATION = re.compile(r"(\d{4}_[a-z0-9_]+)\.py")


def expected_migrations(root=ROOT):
    """{schema: [migration names]} from the repository at the release commit."""
    expected = {}
    for service in SERVICES:
        directory = Path(root) / "services" / service / "service" / "migrations"
        names = sorted(m.group(1) for f in directory.glob("0*.py") if (m := MIGRATION.fullmatch(f.name))) \
            if directory.is_dir() else []
        expected[service] = names
    return expected


def read_password(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise SystemExit("The password file must be a regular owner-only file")
    value = path.read_text().strip()
    if not value:
        raise SystemExit("The password file is empty")
    return value


def connect(host, port, dbname, user, password, sslrootcert):
    import psycopg

    connection = psycopg.connect(host=host, port=port, dbname=dbname, user=user, password=password,
                                 sslmode="verify-full", sslrootcert=sslrootcert, connect_timeout=5,
                                 options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS} -c default_transaction_read_only=on")
    connection.read_only = True  # BEGIN READ ONLY for every transaction on this connection
    return connection


def _scalar(cursor, query, params=()):
    cursor.execute(query, params)
    row = cursor.fetchone()
    return row[0] if row else None


def _table_exists(cursor, schema, table):
    return _scalar(cursor, "SELECT to_regclass(%s) IS NOT NULL", (f'"{schema}"."{table}"',))


def run_checks(connection, expected, *, show_handles=False):
    """The report: {'verdict': 'ok'|'stop', 'stops': [...], ...}. Only SELECT statements are executed."""
    report = {"stops": [], "notes": []}
    with connection.cursor() as cursor:
        report["server"] = {
            "version": _scalar(cursor, "SHOW server_version"),
            "transaction_read_only": _scalar(cursor, "SHOW transaction_read_only"),
            "tls": bool(_scalar(cursor, "SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")),
            "login": _scalar(cursor, "SELECT current_user"),
        }
        if report["server"]["transaction_read_only"] != "on":
            report["stops"].append("The session is not read-only; refusing to continue")
            return _finish(report)
        if not report["server"]["tls"]:
            report["stops"].append("The connection is not using TLS")
        report["server"]["major"] = int(report["server"]["version"].split(".")[0])
        if report["server"]["major"] != 16:
            report["notes"].append("PostgreSQL major version is not 16 (the version the plan assumes)")
        schemas = {r[0] for r in _rows(cursor, "SELECT nspname FROM pg_namespace")}
        report["schemas_missing"] = sorted(set(SERVICES) - schemas)
        if report["schemas_missing"]:
            report["stops"].append("Service schemas are missing: " + ", ".join(report["schemas_missing"]))
        migrations = {}
        for service in SERVICES:
            names = expected.get(service, [])
            if service not in schemas or not _table_exists(cursor, service, "django_migrations"):
                migrations[service] = {"applied": None, "pending": names, "ahead_of_code": [],
                                       "note": "no migration history: every migration is pending"}
                continue
            cursor.execute(f'SELECT name FROM "{service}".django_migrations WHERE app = %s ORDER BY id', ("service",))
            applied = [r[0] for r in cursor.fetchall()]
            pending = [n for n in names if n not in applied]
            ahead = [n for n in applied if n not in names]
            migrations[service] = {"applied": len(applied), "pending": pending, "ahead_of_code": ahead}
            if ahead:
                report["stops"].append(f"{service}: the database has migrations this release does not: {', '.join(ahead)}")
        report["migrations"] = migrations
        report["pending_total"] = sum(len(m["pending"]) for m in migrations.values())

        collisions = {"table_present": False}
        if "creators" in schemas and _table_exists(cursor, "creators", "service_creatorprofile"):
            collisions["table_present"] = True
            collisions["profiles"] = _scalar(cursor, 'SELECT count(*) FROM "creators".service_creatorprofile')
            cursor.execute('SELECT lower(handle), count(*), array_agg(handle ORDER BY handle) '
                           'FROM "creators".service_creatorprofile GROUP BY lower(handle) HAVING count(*) > 1')
            groups = cursor.fetchall()
            collisions["colliding_groups"] = len(groups)
            collisions["rows_in_collisions"] = sum(g[1] for g in groups)
            if show_handles:
                collisions["groups"] = [g[2] for g in groups]
            constraint = _scalar(cursor, "SELECT count(*) FROM pg_constraint WHERE conname = 'creator_handle_case_insensitive'") \
                or _scalar(cursor, "SELECT count(*) FROM pg_indexes WHERE schemaname = 'creators' AND indexname = 'creator_handle_case_insensitive'")
            collisions["constraint_already_present"] = bool(constraint)
            pending_0004 = "0004_creator_profile_fields" in migrations["creators"]["pending"]
            if groups and pending_0004:
                report["stops"].append(f"creators 0004 would fail: {len(groups)} handle group(s) differ only by case; "
                                       "resolve them manually (nothing is renamed automatically)")
        else:
            report["notes"].append("creators profile table not found; handle check skipped")
        report["creator_handles"] = collisions

        stream = {"column_present": False}
        if "content" in schemas and _table_exists(cursor, "content", "service_video"):
            stream["column_present"] = bool(_scalar(
                cursor, "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'content' "
                        "AND table_name = 'service_video' AND column_name = 'stream_upload_id'"))
            stream["videos"] = _scalar(cursor, 'SELECT count(*) FROM "content".service_video')
            if stream["column_present"]:
                stream["rows_with_value"] = _scalar(
                    cursor, 'SELECT count(*) FROM "content".service_video WHERE stream_upload_id IS NOT NULL')
                if stream["rows_with_value"]:
                    report["stops"].append("content 0005 drops stream_upload_id but it holds data; needs owner review")
        report["content_stream_upload_id"] = stream

        report["new_schemas"] = {s: {"present": s in schemas,
                                     "tables": _scalar(cursor, "SELECT count(*) FROM information_schema.tables "
                                                               "WHERE table_schema = %s", (s,)) if s in schemas else 0}
                                 for s in ("engagement", "moderation")}
        report["roles_kolovibe"] = sorted(r[0] for r in _rows(
            cursor, "SELECT rolname FROM pg_roles WHERE rolname LIKE 'kolovibe\\_%' OR rolname LIKE 'kv\\_%'"))
    connection.rollback()
    return _finish(report)


def _rows(cursor, query):
    cursor.execute(query)
    return cursor.fetchall()


def _finish(report):
    report["verdict"] = "stop" if report["stops"] else "ok"
    report["writes_performed"] = 0
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--dbname", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--sslrootcert", required=True)
    parser.add_argument("--show-handles", action="store_true",
                        help="print colliding creator handles to this terminal for manual review")
    args = parser.parse_args(argv)
    connection = connect(args.host, args.port, args.dbname, args.user, read_password(args.password_file), args.sslrootcert)
    try:
        report = run_checks(connection, expected_migrations(), show_handles=args.show_handles)
    finally:
        connection.close()
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["verdict"] == "ok" else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 - never echo connection details or driver text
        print("BLOCKED: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
