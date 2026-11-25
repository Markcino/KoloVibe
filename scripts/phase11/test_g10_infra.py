"""Phase 11, test group 10: infrastructure and security on the disposable stack.

Everything here is local and disposable. AWS, the deployed broker, real TLS termination, image scans and alerting are NOT
exercised (see the infrastructure assessment). Tests that expose a gap in the repository's own database design are expected
to FAIL and say so; they are not softened.
"""

import itertools
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path

import lib
from psycopg import sql


def S():
    return lib.CURRENT


SERVICES = ("identity", "creators", "content", "engagement", "points", "moderation", "audit", "business")


def admin():
    import psycopg

    env = S().environments["identity"]
    password = (S().base / "admin-password").read_text()
    return psycopg.connect(dbname="kolovibe_ci", user="kolovibe_ci_admin", host="127.0.0.1", port=env["KOLOVIBE_DB_PORT"],
                           password=password, sslmode="verify-full", sslrootcert=env["KOLOVIBE_DB_SSLROOTCERT"], autocommit=True)


def raw(port, method, path, headers=None, body=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        r = conn.getresponse()
        data = r.read(200000)
        return r.status, {k.lower(): v for k, v in r.getheaders()}, data
    finally:
        conn.close()


class Database(unittest.TestCase):
    def test_T10_01_a_service_login_cannot_read_another_services_tables(self):
        import psycopg

        with admin() as a:
            first = {svc: a.execute("select table_name from information_schema.tables where table_schema=%s and table_type='BASE TABLE' order by 1 limit 1", (svc,)).fetchone() for svc in SERVICES}
        leaks = []
        for mine, theirs in itertools.permutations(SERVICES, 2):
            if not first[theirs]:
                continue
            with S().db(mine) as c:
                try:
                    c.execute(sql.SQL("select 1 from {}.{} limit 1").format(sql.Identifier(theirs), sql.Identifier(first[theirs][0])))
                    leaks.append((mine, theirs))
                except psycopg.errors.InsufficientPrivilege:
                    pass
        self.assertEqual(leaks, [], f"cross-service reads possible: {leaks[:5]}")

    def test_T10_02_a_service_login_has_no_superuser_file_program_or_ddl_reach(self):
        import psycopg

        with S().db("points") as c:
            for sql in ("select * from pg_authid limit 1", "select pg_read_file('/etc/passwd')", "copy (select 1) to program 'id'",
                        "create extension if not exists pgcrypto", "create schema rogue", "create table public.rogue(x int)",
                        "create role rogue login", "alter system set work_mem='1GB'"):
                with self.assertRaises(psycopg.Error, msg=sql):
                    c.execute(sql)

    def test_T10_03_a_service_login_cannot_switch_off_the_append_only_guards_on_its_own_ledger(self):
        """R-01: the runtime login inherits the role that OWNS its tables, so it can drop the triggers that make its ledger append-only."""
        import psycopg

        problems = []
        for service, table in (("points", "points_entries"), ("audit", "service_securityevent"), ("identity", "service_securityevent")):
            c = S().db(service)
            try:
                c.autocommit = False
                try:
                    c.execute(sql.SQL("alter table {}.{} disable trigger user").format(sql.Identifier(service), sql.Identifier(table)))
                    problems.append((service, table, "trigger disabled by the runtime login"))
                except psycopg.errors.InsufficientPrivilege:
                    pass
            finally:
                c.rollback()
                c.close()
        self.assertEqual(problems, [], f"append-only guards can be disabled by the service's own login: {problems}")

    def test_T10_04_service_logins_do_not_inherit_the_role_that_owns_their_tables(self):
        with admin() as a:
            rows = a.execute("""select schemaname, count(*) filter (where pg_has_role(%s || schemaname, tableowner, 'USAGE')) as inherited, count(*)
                                from pg_tables where schemaname = any(%s) group by 1 order by 1""",
                             ("ci_", list(SERVICES))).fetchall()
        # the login ci_<svc> is a member of kolovibe_<svc>, which owns the tables
        with admin() as a:
            exposed = a.execute("""select t.schemaname, count(*) from pg_tables t where t.schemaname = any(%s)
                                   and pg_has_role('ci_' || t.schemaname, t.tableowner, 'USAGE') group by 1 order by 1""", (list(SERVICES),)).fetchall()
            total = a.execute("select count(*) from pg_tables where schemaname = any(%s)", (list(SERVICES),)).fetchone()[0]
        self.assertEqual(exposed, [], f"{sum(n for _, n in exposed)} of {total} service tables are owned by a role their runtime login inherits (R-01)")

    def test_T10_05_database_connections_require_verified_tls(self):
        import psycopg

        env = S().environments["identity"]
        password = Path(env["KOLOVIBE_DB_PASSWORD_FILE"]).read_text()
        common = dict(dbname="kolovibe_ci", user=env["KOLOVIBE_DB_USER"], host="127.0.0.1", port=env["KOLOVIBE_DB_PORT"], password=password)
        with self.assertRaises(psycopg.OperationalError):
            psycopg.connect(sslmode="disable", **common)
        with self.assertRaises(psycopg.OperationalError):
            psycopg.connect(sslmode="verify-full", sslrootcert=env["KOLOVIBE_DB_SSLROOTCERT"], **{**common, "host": "unapproved.example.test", "hostaddr": "127.0.0.1"})
        with self.assertRaises(psycopg.OperationalError):
            psycopg.connect(sslmode="verify-full", sslrootcert=env["KOLOVIBE_DB_SSLROOTCERT"], **{**common, "password": "wrong-password"})

    def test_T10_06_database_secrets_are_private_files_and_never_in_process_arguments(self):
        for service, env in S().environments.items():
            if "KOLOVIBE_DB_PASSWORD_FILE" not in env:
                continue
            mode = Path(env["KOLOVIBE_DB_PASSWORD_FILE"]).stat().st_mode & 0o777
            self.assertEqual(mode & 0o077, 0, f"{service} password file mode {oct(mode)}")
        passwords = [Path(e["KOLOVIBE_DB_PASSWORD_FILE"]).read_text() for e in S().environments.values() if "KOLOVIBE_DB_PASSWORD_FILE" in e]
        leaked = []
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                try:
                    cmd = (entry / "cmdline").read_bytes().decode(errors="ignore")
                except OSError:
                    continue
                leaked += [entry.name for p in passwords if p and p in cmd]
        self.assertEqual(leaked, [], "a database password appears in a process command line")

    def test_T10_30_a_backup_restores_completely_and_the_guards_survive(self):
        """The tested backup and recovery drill the pre-test rules ask for, on the disposable fixture (not on staging)."""
        import psycopg

        env = S().environments["identity"]
        port, cert = env["KOLOVIBE_DB_PORT"], env["KOLOVIBE_DB_SSLROOTCERT"]
        password = (S().base / "admin-password").read_text()
        dump = S().base / "drill.dump"
        run_env = {**os.environ, "PGPASSWORD": password, "PGSSLMODE": "verify-full", "PGSSLROOTCERT": cert}
        started = time.monotonic()
        subprocess.run(["pg_dump", "-Fc", "-h", "127.0.0.1", "-p", port, "-U", "kolovibe_ci_admin", "-f", str(dump), "kolovibe_ci"], env=run_env, check=True, timeout=300)
        with admin() as a:
            a.execute("drop database if exists kolovibe_restore")
            a.execute("create database kolovibe_restore")
        subprocess.run(["pg_restore", "-h", "127.0.0.1", "-p", port, "-U", "kolovibe_ci_admin", "-d", "kolovibe_restore", "--no-owner", str(dump)], env=run_env,
                       timeout=300, capture_output=True)
        seconds = time.monotonic() - started

        def counts(db):
            with psycopg.connect(dbname=db, user="kolovibe_ci_admin", host="127.0.0.1", port=port, password=password, sslmode="verify-full", sslrootcert=cert, autocommit=True) as c:
                tables = c.execute("select schemaname, tablename from pg_tables where schemaname = any(%s) order by 1,2", (list(SERVICES) + ["gateway"],)).fetchall()
                result = {f"{s}.{t}": c.execute(sql.SQL("select count(*) from {}.{}").format(sql.Identifier(s), sql.Identifier(t))).fetchone()[0] for s, t in tables}
                triggers = c.execute("select count(*) from pg_trigger where not tgisinternal").fetchone()[0]
                return result, triggers

        original, restored = counts("kolovibe_ci"), counts("kolovibe_restore")
        self.assertEqual(original[0], restored[0], "row counts differ after restore")
        self.assertGreater(sum(original[0].values()), 50, "the drill must run on a database that holds data")
        self.assertEqual(original[1], restored[1], "triggers (the append-only guards) must survive a restore")
        with psycopg.connect(dbname="kolovibe_restore", user="kolovibe_ci_admin", host="127.0.0.1", port=port, password=password, sslmode="verify-full", sslrootcert=cert) as c:
            with self.assertRaises(psycopg.Error):
                c.execute("update audit.service_securityevent set kind='tampered'")
                if c.execute("select count(*) from audit.service_securityevent").fetchone()[0] == 0:
                    raise psycopg.Error("no rows to tamper with")  # nothing to test against would be a vacuous pass
        self.assertLess(seconds, 120, f"drill took {seconds:.0f}s")

    def test_T10_31_migrations_are_idempotent_and_the_latest_ones_reverse_and_reapply(self):
        for service in SERVICES:
            env = dict(S().environments[service], KOLOVIBE_ENV="local")
            result = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=lib.ROOT / "services" / service, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, (service, result.stderr[-300:]))
            self.assertIn("No migrations to apply", result.stdout, service)
        failures = []
        for service, back in (("engagement", "0005"), ("business", "0006"), ("creators", "0005")):
            # Phase 12 (D11-002): schema changes are the migration login's job; the runtime login can no longer alter tables.
            base = S().environments[service]
            env = dict(base, KOLOVIBE_ENV="local", KOLOVIBE_DB_USER=base["KOLOVIBE_PG_MIGRATION_USER"],
                       KOLOVIBE_DB_PASSWORD_FILE=base["KOLOVIBE_PG_MIGRATION_PASSWORD_FILE"], KOLOVIBE_DB_MIGRATION_ROLE="kolovibe_" + service)
            for target in (back, None):
                args = [sys.executable, "manage.py", "migrate", "--noinput"] + (["service", target] if target else [])
                result = subprocess.run(args, cwd=lib.ROOT / "services" / service, env=env, capture_output=True, text=True, timeout=120)
                if result.returncode:
                    failures.append((service, target or "forward", result.stderr.strip().splitlines()[-1][:160] if result.stderr.strip() else ""))
        self.assertEqual(failures, [], failures)
        # tables the owner re-created by that round trip must still be usable by the runtime login (default privileges)
        unreachable = []
        for service in ("engagement", "business", "creators"):
            conn = S().db(service)
            try:
                tables = [row[0] for row in conn.execute("select tablename from pg_tables where schemaname = %s", (service,)).fetchall()]
                for table in tables:
                    try:
                        conn.execute(sql.SQL("select 1 from {}.{} limit 1").format(sql.Identifier(service), sql.Identifier(table)))
                    except Exception as error:
                        conn.rollback()
                        unreachable.append((service, table, type(error).__name__))
            finally:
                conn.close()
        self.assertEqual(unreachable, [], "the runtime login lost access to re-created tables: " + str(unreachable[:5]))


class Perimeter(unittest.TestCase):
    def test_T10_10_internal_service_ports_refuse_every_unsigned_request(self):
        found = {}
        for service in SERVICES:
            text = (lib.ROOT / "services" / service / "service" / "urls.py").read_text()
            found[service] = sorted(set(re.findall(r'path\("(internal/[^"<]*|health/ready)', text)))
        refused, allowed = 0, []
        for service, paths in found.items():
            for path in paths:
                for method in ("GET", "POST"):
                    status, _, body = raw(S().ports[service], method, "/" + path.rstrip("/"), {"Content-Type": "application/json"}, "{}" if method == "POST" else None)
                    if status in (200, 201, 204):
                        allowed.append((service, method, path, status))
                    else:
                        refused += 1
        self.assertEqual(allowed, [], f"unsigned internal calls were accepted: {allowed[:5]}")
        self.assertGreater(refused, 40, "too few internal routes were probed")

    def test_T10_11_spoofed_identity_and_forwarding_headers_do_not_open_internal_routes(self):
        spoof = {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1", "X-Service-Caller": "gateway", "X-KoloVibe-Caller": "gateway",
                 "X-Gateway-Actor": str(uuid.uuid4()), "X-Actor-Role": "administrator", "Authorization": "Bearer administrator", "Content-Type": "application/json"}
        for service in ("identity", "points", "business", "audit"):
            status, _, _ = raw(S().ports[service], "POST", "/internal/probe", spoof, "{}")
            self.assertIn(status, (401, 403, 404, 405), f"{service} -> {status}")
        for path in ("/api/v1/internal/likes", "/internal/likes", "/api/v1/internal/security-events", "/internal/probe"):
            status, _, _ = raw(S().ports["gateway"], "POST", path, spoof, "{}")
            self.assertIn(status, (401, 403, 404, 405), f"gateway {path} -> {status}")

    def test_T10_20_no_cors_is_granted_and_dangerous_methods_are_refused(self):
        origin = {"Origin": "https://evil.example"}
        for method, path in (("GET", "/api/v1/videos"), ("OPTIONS", "/api/v1/me"), ("GET", "/api/v1/me"), ("POST", "/api/v1/auth/login")):
            status, headers, _ = raw(S().ports["gateway"], method, path, {**origin, "Access-Control-Request-Method": "GET"})
            self.assertNotIn("access-control-allow-origin", headers, f"{method} {path} granted CORS")
        for method in ("TRACE", "CONNECT", "PROPFIND"):
            status, _, _ = raw(S().ports["gateway"], method, "/api/v1/me")
            self.assertIn(status, (400, 404, 405, 501), f"{method} -> {status}")

    def test_T10_21_path_and_method_tricks_do_not_bypass_authorization(self):
        _, tokens = S().signed_in()
        token = {"Authorization": "Bearer " + tokens["access_token"], "Content-Type": "application/json"}
        paths = ["//api/v1/admin/accounts/lookup", "/api/v1//admin/accounts/lookup", "/api/v1/admin/./accounts/lookup", "/api/v1/admin/accounts/lookup/",
                 "/API/V1/admin/accounts/lookup", "/api/v1/%61dmin/accounts/lookup", "/api/v1/admin%2faccounts/lookup", "/api/v1/me/../admin/accounts/lookup",
                 "/api/v1/admin/accounts/lookup;x=1", "/api/v1/admin/accounts/lookup%00", "/api/v1/admin/accounts/lookup?_method=GET"]
        for path in paths:
            for extra in ({}, {"X-HTTP-Method-Override": "GET"}, {"X-Original-URL": "/api/v1/me"}):
                status, _, body = raw(S().ports["gateway"], "POST", path, {**token, **extra}, json.dumps({"email": "a@example.test"}))
                self.assertNotIn(status, (200, 201, 204), f"{path} {extra} -> {status}")
                self.assertNotIn(b"Traceback", body)

    def test_T10_22_oversized_headers_bodies_and_urls_are_refused_and_the_service_stays_up(self):
        port = S().ports["gateway"]
        cases = [("GET", "/api/v1/videos?" + "a=" + "b" * 60000, {}, None), ("GET", "/api/v1/videos", {"X-Big": "x" * 70000}, None),
                 ("POST", "/api/v1/auth/login", {"Content-Type": "application/json"}, "x" * 3_000_000),
                 ("GET", "/api/v1/videos", {f"X-H{i}": "1" for i in range(300)}, None), ("GET", "/api/v1/videos/%00", {}, None), ("GET", "/api/v1/" + "a" * 8000, {}, None)]
        for method, path, headers, body in cases:
            try:
                status, _, data = raw(port, method, path, headers, body)
            except (ConnectionError, OSError):
                continue  # the server closed the connection: also a refusal
            self.assertLess(status, 500, f"{method} {path[:40]} -> {status}")
        self.assertEqual(raw(port, "GET", "/health/live")[0], 200, "the gateway must still be healthy afterwards")

    def test_T10_23_a_burst_of_public_reads_does_not_cause_server_errors(self):
        port = S().ports["gateway"]

        def one(_):
            started = time.monotonic()
            status = raw(port, "GET", "/api/v1/videos?limit=5")[0]
            return status, time.monotonic() - started

        with ThreadPoolExecutor(32) as pool:
            results = list(pool.map(one, range(400)))
        statuses = [s for s, _ in results]
        self.assertFalse([s for s in statuses if s >= 500], f"server errors under burst: {sorted(set(statuses))}")
        latencies = sorted(t for _, t in results)
        print(f"   burst: 400 requests, 32 concurrent, p50 {latencies[200]*1000:.0f} ms, p95 {latencies[380]*1000:.0f} ms, throttled (429): {statuses.count(429)}", flush=True)
        # Recorded, not asserted: whether an application-level limit exists on public reads is a finding for the infrastructure assessment.

    def test_T10_24_hostile_json_and_unicode_do_not_cause_server_errors(self):
        port = S().ports["gateway"]
        bodies = ['{"email":"\\u0000@example.test","password":"x","display_name":"y"}', '{"a":' * 5000, '[' * 100000, '{"email":"a@b.test","email":"c@d.test","password":"x"}',
                  '{"email":"' + "\U0001F600" * 3000 + '@example.test","password":"x","display_name":"y"}', "﻿{}", '{"password":NaN}', '{"password":1e999999}']
        for body in bodies:
            status, _, data = raw(port, "POST", "/api/v1/auth/register", {"Content-Type": "application/json"}, body.encode("utf-8", "surrogatepass"))
            self.assertLess(status, 500, f"{body[:30]!r} -> {status}")
            self.assertNotIn(b"Traceback", data)


class ZSecretsAndLogs(unittest.TestCase):
    def test_T10_90_no_credential_or_token_created_during_the_run_appears_in_any_service_log(self):
        secrets_found = [s for s in S().secrets if s and len(s) >= 8]
        self.assertGreater(len(secrets_found), 40, "too few secrets were registered for this check to mean anything")
        hits = []
        for log in list(S().base.glob("*.log")):
            text = log.read_text(errors="ignore")
            for value in secrets_found:
                if value in text:
                    hits.append((log.name, value[:6] + "…"))
            for pattern in (r"Bearer [A-Za-z0-9_\-]{20,}", r"refresh_token[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_\-]{20,}", r"password[\"']?\s*[:=]\s*[\"'][^\"']{8,}"):
                if re.search(pattern, text):
                    hits.append((log.name, pattern[:20]))
        self.assertEqual(hits, [], f"secrets found in logs: {hits[:6]}")

    def test_T10_91_service_logs_record_requests_without_query_strings_that_carry_secrets(self):
        code = S().post("/auth/verify", {"email": "nobody@example.test", "code": "123456"})[0]
        S().get("/videos?cursor=sensitive-looking-value-12345")
        text = (S().base / "gateway.log").read_text(errors="ignore")
        self.assertNotIn("123456", text)
