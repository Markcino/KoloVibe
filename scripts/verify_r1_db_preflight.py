"""Prove the R1 read-only database preflight on a disposable, fully migrated PostgreSQL (TLS, verify-full).

Cases: a clean database passes; pending migrations, a database ahead of the code, legacy handle collisions that would
break creators 0004, and stream_upload_id data each stop the plan; the session is read-only so even an INSERT through
the tool's connection fails; no handle appears in the default output; the password file must be owner-only.
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / "ops"))

import r1_db_preflight as preflight  # noqa: E402
from test_postgres_foundations import postgres_fixture  # noqa: E402

OPS = Path(__file__).resolve().parent / "ops" / "r1_db_preflight.py"


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = postgres_fixture()
        cls.base, cls.environments = cls.context.__enter__()
        env = cls.environments["gateway"]
        cls.params = dict(host="127.0.0.1", port=int(env["KOLOVIBE_DB_PORT"]), dbname=env["KOLOVIBE_DB_NAME"],
                          sslrootcert=env["KOLOVIBE_DB_SSLROOTCERT"])
        cls.admin_password = (cls.base / "admin-password").read_text()
        cls.expected = preflight.expected_migrations()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def admin(self):
        import psycopg

        return psycopg.connect(user="kolovibe_ci_admin", password=self.admin_password, sslmode="verify-full",
                               autocommit=True, **self.params)

    def check(self, **kw):
        connection = preflight.connect(user="kolovibe_ci_admin", password=self.admin_password, **self.params)
        try:
            return preflight.run_checks(connection, self.expected, **kw)
        finally:
            connection.close()

    def test_a_fully_migrated_clean_database_passes_and_writes_nothing(self):
        report = self.check()
        self.assertEqual(report["verdict"], "ok", report["stops"])
        self.assertEqual(report["pending_total"], 0)
        self.assertEqual(report["server"]["transaction_read_only"], "on")
        self.assertTrue(report["server"]["tls"])
        self.assertEqual(report["writes_performed"], 0)
        self.assertEqual(report["creator_handles"]["colliding_groups"], 0)
        self.assertTrue(report["creator_handles"]["constraint_already_present"])

    def test_the_connection_cannot_write_even_by_mistake(self):
        import psycopg

        connection = preflight.connect(user="kolovibe_ci_admin", password=self.admin_password, **self.params)
        try:
            with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
                connection.execute("CREATE TABLE public.should_not_exist (id integer)")
            connection.rollback()
            with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
                connection.execute('DELETE FROM "creators".django_migrations')
        finally:
            connection.close()
        with self.admin() as db:
            self.assertIsNone(db.execute("SELECT to_regclass('public.should_not_exist')").fetchone()[0])
            self.assertGreater(db.execute('SELECT count(*) FROM "creators".django_migrations').fetchone()[0], 0)

    def test_pending_migrations_are_listed_and_do_not_stop_the_plan(self):
        with self.admin() as db:
            db.execute("""DELETE FROM "engagement".django_migrations WHERE app = 'service'""")
            db.execute("""DELETE FROM "points".django_migrations WHERE name = '0005_audit_evidence'""")
        try:
            report = self.check()
            self.assertEqual(report["verdict"], "ok", report["stops"])
            self.assertEqual(report["migrations"]["points"]["pending"], ["0005_audit_evidence"])
            self.assertEqual(len(report["migrations"]["engagement"]["pending"]), 6)
            self.assertEqual(report["pending_total"], 7)
        finally:
            with self.admin() as db:  # restore the fixture rows for the other cases (disposable test database)
                db.execute("""INSERT INTO "engagement".django_migrations (app, name, applied)
                              SELECT 'service', n, now() FROM unnest(%s::text[]) n""", (self.expected["engagement"],))
                db.execute("""INSERT INTO "points".django_migrations (app, name, applied)
                              VALUES ('service', '0005_audit_evidence', now())""")

    def test_a_database_ahead_of_the_code_stops_the_plan(self):
        with self.admin() as db:
            db.execute("""INSERT INTO "audit".django_migrations (app, name, applied) VALUES ('service', '0099_future', now())""")
        try:
            report = self.check()
            self.assertEqual(report["verdict"], "stop")
            self.assertTrue(any("audit" in stop and "0099_future" in stop for stop in report["stops"]))
        finally:
            with self.admin() as db:
                db.execute("""DELETE FROM "audit".django_migrations WHERE name = '0099_future'""")

    def test_case_only_handle_collisions_stop_the_plan_when_0004_is_pending_and_hide_handles(self):
        with self.admin() as db:
            db.execute('ALTER TABLE "creators".service_creatorprofile DROP CONSTRAINT IF EXISTS creator_handle_case_insensitive')
            db.execute('DROP INDEX IF EXISTS "creators".creator_handle_case_insensitive')
            db.execute("""INSERT INTO "creators".service_creatorprofile
                          (id, user_id, handle, display_name, location, bio, status, created_at)
                          VALUES (gen_random_uuid(), gen_random_uuid(), 'Ama_K', '', '', '', 'pending', now()),
                                 (gen_random_uuid(), gen_random_uuid(), 'ama_k', '', '', '', 'pending', now()),
                                 (gen_random_uuid(), gen_random_uuid(), 'unique_one', '', '', '', 'pending', now())""")
            db.execute("""DELETE FROM "creators".django_migrations WHERE name = '0004_creator_profile_fields'""")
        try:
            report = self.check()
            self.assertEqual(report["verdict"], "stop")
            self.assertEqual(report["creator_handles"]["colliding_groups"], 1)
            self.assertEqual(report["creator_handles"]["rows_in_collisions"], 2)
            self.assertTrue(any("creators 0004 would fail" in stop for stop in report["stops"]))
            self.assertNotIn("Ama_K", json.dumps(report))
            self.assertNotIn("ama_k", json.dumps(report))
            shown = self.check(show_handles=True)
            self.assertEqual(sorted(shown["creator_handles"]["groups"][0]), ["Ama_K", "ama_k"])
        finally:
            with self.admin() as db:
                db.execute("""DELETE FROM "creators".service_creatorprofile WHERE lower(handle) IN ('ama_k', 'unique_one')""")
                db.execute("""INSERT INTO "creators".django_migrations (app, name, applied)
                              VALUES ('service', '0004_creator_profile_fields', now())""")
                db.execute("""CREATE UNIQUE INDEX creator_handle_case_insensitive
                              ON "creators".service_creatorprofile (lower(handle))""")

    def test_collisions_do_not_stop_a_database_whose_0004_is_already_applied(self):
        # Cannot occur while the constraint exists; the verdict only depends on pending 0004.
        report = self.check()
        self.assertEqual(report["verdict"], "ok", report["stops"])

    def test_stream_upload_id_data_is_reported_and_stops_the_plan(self):
        defaults = {"uuid": "gen_random_uuid()", "character varying": "'x'", "text": "'x'", "integer": "0", "bigint": "0",
                    "smallint": "0", "boolean": "false", "timestamp with time zone": "now()", "jsonb": "'{}'::jsonb"}
        with self.admin() as db:
            db.execute('ALTER TABLE "content".service_video ADD COLUMN IF NOT EXISTS stream_upload_id varchar(64)')
            columns = db.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'content' "
                "AND table_name = 'service_video' AND is_nullable = 'NO' AND column_default IS NULL").fetchall()
            from psycopg import sql

            db.execute(sql.SQL("INSERT INTO content.service_video ({names}) VALUES ({values})").format(
                names=sql.SQL(", ").join([sql.Identifier(c) for c, _ in columns] + [sql.Identifier("stream_upload_id")]),
                values=sql.SQL(", ").join([sql.SQL(defaults[t]) for _, t in columns] + [sql.Literal("legacy-upload")])))
        try:
            report = self.check()
            self.assertTrue(report["content_stream_upload_id"]["column_present"])
            self.assertEqual(report["content_stream_upload_id"]["rows_with_value"], 1)
            self.assertEqual(report["verdict"], "stop")
            self.assertTrue(any("stream_upload_id" in stop for stop in report["stops"]))
            self.assertNotIn("legacy-upload", json.dumps(report))
        finally:
            with self.admin() as db:
                db.execute('DELETE FROM "content".service_video WHERE stream_upload_id = %s', ("legacy-upload",))
                db.execute('ALTER TABLE "content".service_video DROP COLUMN IF EXISTS stream_upload_id')
        self.assertEqual(self.check()["verdict"], "ok")

    def test_the_command_line_refuses_a_group_readable_password_file_and_prints_no_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            password = Path(directory) / "pw"
            password.write_text(self.admin_password)
            password.chmod(0o644)
            arguments = [sys.executable, str(OPS), "--host", "127.0.0.1", "--port", str(self.params["port"]),
                         "--dbname", self.params["dbname"], "--user", "kolovibe_ci_admin",
                         "--password-file", str(password), "--sslrootcert", self.params["sslrootcert"]]
            result = subprocess.run(arguments, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(self.admin_password, result.stdout + result.stderr)
            password.chmod(0o600)
            result = subprocess.run(arguments, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["verdict"], "ok")
            self.assertNotIn(self.admin_password, result.stdout + result.stderr)


class SqlScriptTests(unittest.TestCase):
    """The psql variant for operators without a Python path to the database."""

    def run_sql(self, password, port, ca, user="kolovibe_ci_admin", dbname="kolovibe_ci"):
        import os
        import shutil

        psql = shutil.which("psql")
        if psql is None:
            self.skipTest("psql is not installed")
        env = dict(os.environ, PGPASSWORD=password, PGSSLMODE="verify-full", PGSSLROOTCERT=ca, PGGSSENCMODE="disable", PGHOSTADDR="127.0.0.1")
        return subprocess.run([psql, "-X", "-v", "ON_ERROR_STOP=1", "-h", "localhost", "-p", str(port), "-U", user,
                               "-d", dbname, "-f", str(Path(__file__).resolve().parents[1] / "infra/postgres/r1_readonly_preflight.sql")],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_the_sql_script_is_read_only_prints_counts_and_never_selects_handles(self):
        context = postgres_fixture()
        base, environments = context.__enter__()
        try:
            env = environments["gateway"]
            result = self.run_sql((base / "admin-password").read_text(), env["KOLOVIBE_DB_PORT"], env["KOLOVIBE_DB_SSLROOTCERT"],
                                  dbname=env["KOLOVIBE_DB_NAME"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("transaction_read_only", result.stdout)
            self.assertRegex(result.stdout, r"transaction_read_only[\s\S]*\bon\b")
            self.assertIn("0004_creator_profile_fields", result.stdout)
            self.assertRegex(result.stdout, r"colliding_groups[\s\S]*\b0\b")
        finally:
            context.__exit__(None, None, None)
        sql = (Path(__file__).resolve().parents[1] / "infra/postgres/r1_readonly_preflight.sql").read_text()
        code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--") and not line.startswith("\\echo"))
        self.assertNotRegex(code.upper(), r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|COPY)\b")
        self.assertNotRegex(code, r"SELECT\s+handle\b|,\s*handle\s*[,)]|array_agg")
        self.assertTrue(code.lstrip().startswith("\\set QUIET on") or "BEGIN READ ONLY;" in code)
        self.assertTrue(code.rstrip().endswith("ROLLBACK;"))


class PureTests(unittest.TestCase):
    def test_expected_migrations_come_from_the_repository_for_every_service(self):
        expected = preflight.expected_migrations()
        self.assertEqual(set(expected), set(preflight.SERVICES))
        self.assertIn("0004_creator_profile_fields", expected["creators"])
        self.assertIn("0008_video_metadata_and_soft_delete", expected["content"])
        self.assertEqual(len(expected["engagement"]), 6)
        self.assertEqual(expected["gateway"], [])

    def test_only_select_statements_exist_in_the_tool(self):
        source = OPS.read_text()
        statements = [line.strip() for line in source.splitlines() if "cursor.execute(" in line or "_scalar(cursor," in line]
        self.assertTrue(statements)
        for statement in statements:
            self.assertNotRegex(statement.upper(), r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|COPY)\b")


if __name__ == "__main__":
    unittest.main()
