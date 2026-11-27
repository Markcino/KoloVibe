"""Exercise infra/postgres/r01_ownership_remediation.sql against a disposable TLS PostgreSQL (D11-002 / R-01).

The fixture is built in the NEW ownership model; this test first puts one schema back into the OLD (legacy) state, where the
runtime login owns its tables, proves the exposure, runs the remediation script with psql, and proves it is closed while the
login keeps its data access. It also proves the script refuses an unknown service and a missing or privileged login.
"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from scripts.test_postgres_foundations import ROOT, postgres_fixture

SCRIPT = ROOT / "infra" / "postgres" / "r01_ownership_remediation.sql"


def run_script(base, environment, service, login):
    psql = shutil.which("psql")
    env = {"PATH": os.environ.get("PATH", ""), "PGPASSWORD": (base / "admin-password").read_text(), "PGSSLMODE": "verify-full",
           # libpq 14's IP-name verification differs from newer libpq used by
           # psycopg. Verify the fixture's DNS SAN and pin the loopback address;
           # keep verify-full and the private fixture CA on every invocation.
           "PGSSLROOTCERT": environment["KOLOVIBE_DB_SSLROOTCERT"], "PGHOST": "localhost", "PGHOSTADDR": "127.0.0.1",
           "PGPORT": environment["KOLOVIBE_DB_PORT"],
           "PGUSER": "kolovibe_ci_admin", "PGDATABASE": "kolovibe_ci"}
    return subprocess.run([psql, "-X", "-v", "ON_ERROR_STOP=1", "-v", "service=" + service, "-v", "runtime_login=" + login,
                           "-f", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=120)


class RemediationTests(unittest.TestCase):
    @unittest.skipUnless(all(shutil.which(tool) for tool in ("initdb", "pg_ctl", "openssl", "psql")),
                         "needs the PostgreSQL server and client tools (run by the PostgreSQL integration step)")
    def test_the_script_closes_a_legacy_ownership_exposure_and_refuses_bad_input(self):
        import psycopg
        with postgres_fixture() as (base, environments):
            environment = environments["points"]
            connection = dict(dbname="kolovibe_ci", user="kolovibe_ci_admin", host="127.0.0.1", port=environment["KOLOVIBE_DB_PORT"],
                              password=(base / "admin-password").read_text(), sslmode="verify-full",
                              sslrootcert=environment["KOLOVIBE_DB_SSLROOTCERT"], autocommit=True)

            def exposure():
                with psycopg.connect(**connection) as db:
                    return db.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                      "WHERE n.nspname = 'points' AND c.relkind IN ('r','p','S') "
                                      "AND pg_has_role('ci_points', c.relowner, 'USAGE')").fetchone()[0]

            self.assertEqual(exposure(), 0, "the fixture must start in the new model")
            with psycopg.connect(**connection) as db:  # put the schema back into the legacy state
                db.execute("GRANT kolovibe_points TO ci_points")
                db.execute("REVOKE kolovibe_points_rt FROM ci_points")
                db.execute("REASSIGN OWNED BY kolovibe_points TO ci_points")
            self.assertGreater(exposure(), 10, "the legacy state must expose the tables, or this test proves nothing")

            for service, login in (("nonexistent", "ci_points"), ("points", "no_such_login"), ("points", "kolovibe_ci_admin")):
                refused = run_script(base, environment, service, login)
                self.assertNotEqual(refused.returncode, 0, (service, login, refused.stdout))
                self.assertGreater(exposure(), 10, "a refused run must change nothing")

            done = run_script(base, environment, "points", "ci_points")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(exposure(), 0)
            with psycopg.connect(**{**connection, "user": "ci_points",
                                    "password": Path(environment["KOLOVIBE_DB_PASSWORD_FILE"]).read_text()}) as login:
                login.execute("SET search_path = points")
                login.execute("SELECT count(*) FROM event_outbox").fetchone()
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    login.execute("ALTER TABLE points_entries DISABLE TRIGGER USER")
            self.assertEqual(run_script(base, environment, "points", "ci_points").returncode, 0, "the script is re-runnable")


if __name__ == "__main__":
    unittest.main()
