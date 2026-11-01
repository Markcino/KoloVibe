"""Exercise foundation contracts against a disposable, TLS-only PostgreSQL."""

import hashlib
from contextlib import contextmanager
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("gateway", "identity", "creators", "content", "engagement", "points",
            "moderation", "audit")


def run(command, **kwargs):
    subprocess.run(command, check=True, **kwargs)


def secret_file(path, value):
    path.touch(mode=0o600)
    path.write_text(value)


@contextmanager
def postgres_fixture():
    import psycopg
    from psycopg import sql

    tools = {tool: shutil.which(tool) for tool in ("initdb", "pg_ctl", "openssl")}
    missing = [name for name, path in tools.items() if path is None]
    if missing:
        raise RuntimeError("Missing PostgreSQL integration tools: " + ", ".join(missing))
    with tempfile.TemporaryDirectory(prefix="kolovibe-pg-test-") as directory:
        base = Path(directory)
        data = base / "data"
        password = secrets.token_urlsafe(48)
        password_path = base / "admin-password"
        secret_file(password_path, password)
        certificate = base / "server.crt"
        key = base / "server.key"
        run([tools["openssl"], "req", "-new", "-x509", "-nodes", "-days", "1",
             "-newkey", "rsa:2048", "-subj", "/CN=localhost",
             "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
             "-keyout", str(key), "-out", str(certificate)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        key.chmod(0o600)
        run([tools["initdb"], "-D", str(data), "-U", "kolovibe_ci_admin",
             "--no-locale", "--encoding=UTF8", "--auth-local=trust",
             "--auth-host=scram-sha-256", "--pwfile", str(password_path)],
            stdout=subprocess.DEVNULL)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with (data / "postgresql.conf").open("a") as config:
            config.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\nssl=on\n"
                         f"ssl_cert_file='{certificate}'\nssl_key_file='{key}'\n"
                         f"unix_socket_directories='{base}'\n")
        (data / "pg_hba.conf").write_text(
            "hostssl all all 127.0.0.1/32 scram-sha-256\n"
            "hostnossl all all 127.0.0.1/32 reject\n")
        run([tools["pg_ctl"], "-D", str(data), "-l", str(base / "postgres.log"),
             "-w", "start"], stdout=subprocess.DEVNULL)
        try:
            parameters = dict(host="127.0.0.1", port=port, user="kolovibe_ci_admin",
                              password=password, sslmode="verify-full",
                              sslrootcert=str(certificate))
            for changes in ({"sslmode": "disable"},
                            {"host": "unapproved.example.test", "hostaddr": "127.0.0.1"}):
                try:
                    unsafe = psycopg.connect(dbname="postgres", **dict(parameters, **changes))
                except psycopg.OperationalError:
                    continue
                unsafe.close()
                raise AssertionError("PostgreSQL accepted an unprotected or wrong-host connection")
            print("TLS fixture rejects plaintext and wrong-host certificates", flush=True)
            with psycopg.connect(dbname="postgres", autocommit=True, **parameters) as db:
                db.execute("CREATE DATABASE kolovibe_ci")
            with psycopg.connect(dbname="kolovibe_ci", autocommit=True, **parameters) as db:
                db.execute((ROOT / "infra/postgres/schema_isolation.sql").read_text())
                db.execute("REVOKE CREATE ON DATABASE kolovibe_ci FROM PUBLIC")
                environments = {}
                for service in SERVICES:
                    credential = secrets.token_urlsafe(48)
                    credential_path = base / f"{service}-password"
                    secret_file(credential_path, credential)
                    db.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier("ci_" + service), sql.Literal(credential)))
                    db.execute(sql.SQL("GRANT {} TO {}").format(
                        sql.Identifier("kolovibe_" + service),
                        sql.Identifier("ci_" + service)))
                    environment = dict(
                        {name: value for name, value in os.environ.items()
                         if not name.startswith("KOLOVIBE_")},
                        KOLOVIBE_ENV="local", DJANGO_SECRET_KEY=secrets.token_urlsafe(48),
                        KOLOVIBE_DB_NAME="kolovibe_ci", KOLOVIBE_DB_USER="ci_" + service,
                        KOLOVIBE_DB_HOST="127.0.0.1", KOLOVIBE_DB_PORT=str(port),
                        KOLOVIBE_DB_PASSWORD_FILE=str(credential_path),
                        KOLOVIBE_DB_SSLROOTCERT=str(certificate),
                        KOLOVIBE_PG_FIXTURE=str(base),
                        PYTHONPATH=os.pathsep.join((str(ROOT / "services"),
                                                   os.environ.get("PYTHONPATH", ""))),
                        KOLOVIBE_SERVICE_NAME=service)
                    environments[service] = environment
                    run([sys.executable, "manage.py", "migrate", "--noinput"],
                        cwd=ROOT / "services" / service, env=environment)
            yield base, environments
        finally:
            run([tools["pg_ctl"], "-D", str(data), "-m", "fast", "-w", "stop"],
                stdout=subprocess.DEVNULL)


def fixture():
    with postgres_fixture() as (_, environments):
        for service, environment in environments.items():
            run([sys.executable, str(Path(__file__).resolve()), "--service", service],
                env=environment)


def service_tests(service):
    if service not in SERVICES:
        raise ValueError("Unknown service")
    fixture_path = Path(os.environ["KOLOVIBE_PG_FIXTURE"])
    if (not fixture_path.name.startswith("kolovibe-pg-test-")
            or not (fixture_path / "data" / "postmaster.pid").is_file()
            or os.environ["KOLOVIBE_DB_NAME"] != "kolovibe_ci"
            or os.environ["KOLOVIBE_DB_HOST"] != "127.0.0.1"):
        raise RuntimeError("Integration tests require the disposable database fixture")
    sys.path.insert(0, str(ROOT / "services" / service))
    os.environ["DJANGO_SETTINGS_MODULE"] = "service.settings"
    import django
    from psycopg import sql
    django.setup()
    from django.db import DatabaseError, connection, transaction
    from django.http import HttpResponse
    from django.test import RequestFactory
    from service.service_auth import ServiceAuthMiddleware

    class Foundations(unittest.TestCase):
        def test_actual_cross_service_sql_access_is_denied(self):
            with connection.cursor() as cursor:
                cursor.execute("SELECT rolsuper,rolcreatedb,rolcreaterole "
                               "FROM pg_roles WHERE rolname=current_user")
                self.assertEqual(cursor.fetchone(), (False, False, False))
                cursor.execute("SELECT count(*) FROM event_inbox")
            for other in SERVICES:
                if other == service:
                    continue
                for query in (
                    sql.SQL("SELECT * FROM {}.event_inbox").format(sql.Identifier(other)),
                    sql.SQL("DELETE FROM {}.event_inbox").format(sql.Identifier(other)),
                ):
                    with self.subTest(other=other, query=query):
                        with self.assertRaises(DatabaseError):
                            with transaction.atomic(), connection.cursor() as cursor:
                                cursor.execute(query)

        def test_signed_identity_replay_expiry_and_wrong_audience(self):
            key = secrets.token_urlsafe(48)
            with tempfile.TemporaryDirectory(prefix="kolovibe-auth-test-") as directory:
                keys = Path(directory) / "keys.json"
                secret_file(keys, json.dumps({"gateway": key}))
                middleware = ServiceAuthMiddleware(lambda request: HttpResponse(status=200))

                def request(audience=service, stamp=None):
                    stamp = str(int(time.time()) if stamp is None else stamp)
                    nonce = secrets.token_urlsafe(24)
                    canonical = "\n".join(("gateway", audience, stamp, nonce,
                                            "POST", "/internal/probe",
                                            hashlib.sha256(b"{}").hexdigest()))
                    signature = hmac.new(key.encode(), canonical.encode(),
                                         hashlib.sha256).hexdigest()
                    return RequestFactory().post("/internal/probe", data=b"{}",
                        content_type="application/json", HTTP_X_KOLOVIBE_CALLER="gateway",
                        HTTP_X_KOLOVIBE_NONCE=nonce, HTTP_X_KOLOVIBE_TIMESTAMP=stamp,
                        HTTP_X_KOLOVIBE_SIGNATURE=signature)

                with patch.dict(os.environ, KOLOVIBE_CALLER_KEYS_FILE=str(keys),
                                KOLOVIBE_SERVICE_NAME=service):
                    valid = request()
                    self.assertEqual(middleware(valid).status_code, 200)
                    self.assertEqual(middleware(valid).status_code, 403)
                    self.assertEqual(middleware(request(audience="wrongservice")).status_code, 403)
                    self.assertEqual(middleware(request(stamp=int(time.time()) - 120)).status_code, 403)

        def test_outbox_republish_and_transactional_inbox(self):
            if service not in ("points", "engagement"):
                return
            from service import events
            delivered = []

            class Publisher:
                crash = True

                def send_task(self, name, **kwargs):
                    delivered.append((name, kwargs))
                    if self.crash:
                        raise RuntimeError("Simulated crash after broker accepted delivery")

            publisher = Publisher()
            with transaction.atomic():
                event_id = events.record_event("foundation.test", {"fixture": True})
            with self.assertRaises(RuntimeError):
                events.dispatch_one(publisher)
            publisher.crash = False
            self.assertTrue(events.dispatch_one(publisher))
            self.assertFalse(events.dispatch_one(publisher))
            self.assertEqual(delivered[0], delivered[1])
            self.assertEqual(delivered[1][1]["task_id"], event_id)
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    self.assertTrue(events.accept_once(event_id, "foundation.test"))
                    raise RuntimeError("Simulated business transaction rollback")
            with transaction.atomic():
                self.assertTrue(events.accept_once(event_id, "foundation.test"))
                self.assertFalse(events.accept_once(event_id, "foundation.test"))

    names = ["test_actual_cross_service_sql_access_is_denied",
             "test_signed_identity_replay_expiry_and_wrong_audience"]
    if service in ("points", "engagement"):
        names.append("test_outbox_republish_and_transactional_inbox")
    suite = unittest.TestSuite(Foundations(name) for name in names)
    if service == "points":
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName("tests.test_ledger"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    connection.close()
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--service":
        service_tests(sys.argv[2])
    elif len(sys.argv) == 1:
        fixture()
    else:
        raise SystemExit("Usage: test_postgres_foundations.py [--service SERVICE]")
