"""Restricted staging acceptance in disposable PostgreSQL, TLS and mail fixtures."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.client import HTTPConnection, HTTPSConnection, RemoteDisconnected
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import sys
import time
import uuid

from test_postgres_foundations import ROOT, SERVICES, postgres_fixture, secret_file
from verify_local_journeys import fixture_directory, seed, stop


def test_application():
    fixture_directory()
    from staging_runtime.wsgi import application
    from django.conf import settings
    if settings.KOLOVIBE_SERVICE_NAME == "identity":
        settings.EMAIL_BACKEND = "verify_local_journeys.CapturedMail"
    return application


def request(port, path, ca, *, data=None, token=None, host=None):
    context = ssl.create_default_context(cafile=str(ca))
    connection = HTTPSConnection("localhost", port, context=context, timeout=8)
    try:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if host:
            headers["Host"] = host
        connection.request("POST" if data is not None else "GET", path,
                           body=None if data is None else json.dumps(data), headers=headers)
        response = connection.getresponse()
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise AssertionError("Oversized staging response")
        content = (json.loads(raw) if raw and response.getheader("Content-Type", "").startswith(
            "application/json") else raw)
        return response.status, content if raw else None
    finally:
        connection.close()


def check_environment(environment, service, *, succeeds=True):
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=ROOT / "services" / service, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if (result.returncode == 0) != succeeds:
        if succeeds:
            raise AssertionError(f"Unexpected staging deployment check result: {service}\n"
                                 + result.stderr)
        raise AssertionError(f"Invalid staging configuration was accepted: {service}")


def admin_connection(base, environment):
    import psycopg

    return psycopg.connect(
        dbname=environment["KOLOVIBE_DB_NAME"], user="kolovibe_ci_admin",
        host=environment["KOLOVIBE_DB_HOST"], port=environment["KOLOVIBE_DB_PORT"],
        password=(base / "admin-password").read_text(),
        sslmode="verify-full", sslrootcert=environment["KOLOVIBE_DB_SSLROOTCERT"],
        autocommit=True,
    )


def runtime_logins(base, environments):
    import psycopg
    from psycopg import sql

    with admin_connection(base, environments["gateway"]) as connection:
        for service, environment in environments.items():
            user = "stage_" + service
            credential = secrets.token_urlsafe(48)
            path = base / f"{service}-runtime-password"
            secret_file(path, credential)
            connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(user), sql.Literal(credential)))
            for statement in (
                "GRANT USAGE ON SCHEMA {} TO {}",
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}",
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}",
            ):
                connection.execute(sql.SQL(statement).format(
                    sql.Identifier(service), sql.Identifier(user)))
            environment.update(KOLOVIBE_DB_USER=user, KOLOVIBE_DB_PASSWORD_FILE=str(path))
            with psycopg.connect(
                dbname=environment["KOLOVIBE_DB_NAME"], user=user, password=credential,
                host=environment["KOLOVIBE_DB_HOST"], port=environment["KOLOVIBE_DB_PORT"],
                sslmode="verify-full", sslrootcert=environment["KOLOVIBE_DB_SSLROOTCERT"],
            ) as runtime:
                for other in SERVICES:
                    if other == service:
                        continue
                    try:
                        runtime.execute(sql.SQL("SELECT * FROM {}.event_inbox").format(
                            sql.Identifier(other)))
                    except psycopg.errors.InsufficientPrivilege:
                        runtime.rollback()
                    else:
                        raise AssertionError("Staging runtime crossed a service schema boundary")
                try:
                    runtime.execute(sql.SQL("CREATE TABLE {}.unapproved (id integer)").format(
                        sql.Identifier(service)))
                except psycopg.errors.InsufficientPrivilege:
                    runtime.rollback()
                else:
                    raise AssertionError("Staging runtime has migration privileges")


def change_record(environment, query, parameters):
    import psycopg

    with psycopg.connect(
        dbname=environment["KOLOVIBE_DB_NAME"], user=environment["KOLOVIBE_DB_USER"],
        password=Path(environment["KOLOVIBE_DB_PASSWORD_FILE"]).read_text(),
        host=environment["KOLOVIBE_DB_HOST"], port=environment["KOLOVIBE_DB_PORT"],
        sslmode="verify-full", sslrootcert=environment["KOLOVIBE_DB_SSLROOTCERT"],
    ) as connection:
        connection.execute(query, parameters)


def verify():
    with postgres_fixture() as (base, environments), ExitStack() as stack:
        certificate = base / "server.crt"
        key = base / "server.key"
        ports = {}
        reservations = {}
        for service in SERVICES:
            sock = stack.enter_context(socket.socket())
            sock.bind(("127.0.0.1", 0))
            ports[service] = sock.getsockname()[1]
            reservations[service] = sock
        signing = secrets.token_urlsafe(48)
        probe = secrets.token_urlsafe(48)
        callers = base / "callers.json"
        outbound = base / "outbound"
        probe_path = base / "probe"
        peers = base / "peers.json"
        secret_file(callers, json.dumps({"gateway": signing}))
        secret_file(outbound, signing)
        secret_file(probe_path, probe)
        secret_file(peers, json.dumps({name: f"https://127.0.0.1:{ports[name]}"
                                     for name in ("content", "creators")}))
        creator_id = uuid.uuid4()
        video_id = uuid.uuid4()
        seed(environments["creators"], creator_id, [video_id])
        seed(environments["content"], creator_id, [video_id])
        runtime_logins(base, environments)
        processes = {}
        for service in SERVICES:
            environment = environments[service]
            django_key = base / f"{service}-django"
            secret_file(django_key, secrets.token_urlsafe(48))
            environment.update(
                KOLOVIBE_ENV="staging", DJANGO_DEBUG="0",
                DJANGO_SECRET_KEY_FILE=str(django_key),
                KOLOVIBE_ALLOWED_HOSTS="127.0.0.1",
                KOLOVIBE_TLS_CERT_FILE=str(certificate), KOLOVIBE_TLS_KEY_FILE=str(key),
                KOLOVIBE_INTERNAL_CA_FILE=str(certificate),
                KOLOVIBE_CALLER_KEYS_FILE=str(callers), KOLOVIBE_PROBE_TOKEN_FILE=str(probe_path),
                KOLOVIBE_TRUSTED_PEERS_FILE=str(peers),
                KOLOVIBE_OUTBOUND_KEY_FILE=str(outbound),
                PYTHONPATH=os.pathsep.join((str(ROOT / "services"), str(ROOT / "scripts"))))
            # localhost is deliberately forbidden as a staging Host; TLS still verifies it.
            check_environment(environment, service)
            for name, invalid in (
                ("KOLOVIBE_ENV", "production"), ("DJANGO_DEBUG", "1"),
                ("KOLOVIBE_ALLOWED_HOSTS", "*"), ("DJANGO_SECRET_KEY_FILE", ""),
                ("KOLOVIBE_DB_PASSWORD_FILE", ""), ("KOLOVIBE_INTERNAL_CA_FILE", "/missing"),
                ("KOLOVIBE_STAGING_ACCOUNTS", "1"),
            ):
                check_environment(dict(environment, **{name: invalid}), service, succeeds=False)
            log = stack.enter_context((base / f"staging-{service}.log").open("w"))
            reservations[service].close()
            process = subprocess.Popen(
                [sys.executable, "-m", "gunicorn", "--config",
                 str(ROOT / "services/staging_runtime/gunicorn.conf.py"),
                 "--bind", f"127.0.0.1:{ports[service]}", "--workers", "1",
                 "verify_staging_runtime:test_application()"],
                cwd=ROOT / "services" / service, env=environment, stdout=log, stderr=log)
            stack.callback(stop, process)
            processes[service] = process
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise AssertionError(f"Staging Gunicorn exited before liveness: {service}")
                try:
                    status, body = request(ports[service], "/health/live", certificate, host="127.0.0.1")
                    if status == 200 and body == {"status": "ok"}:
                        break
                except (OSError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise AssertionError(f"Staging Gunicorn liveness timeout: {service}")
                time.sleep(0.1)
        host = {"host": "127.0.0.1"}

        def api(service, path, **kwargs):
            return request(ports[service], path, certificate, **host, **kwargs)

        for service in SERVICES:
            assert api(service, "/health/ready") == (200, {"status": "ok"}), service
            assert api(service, "/ops/verify")[0] == 403
            assert api(service, "/ops/verify", token=probe) == (200, {"status": "ok"})
            assert api(service, "/internal/probe")[0] == 403
            assert api(service, "/api/v1/points")[0] == 403
            assert request(ports[service], "/health/live", certificate, host="evil.example.test")[0] == 400
        with admin_connection(base, environments["content"]) as connection:
            migration = connection.execute(
                "DELETE FROM content.django_migrations WHERE app=%s AND name=%s "
                "RETURNING id,app,name,applied", ("service", "0002_internal_nonce")).fetchone()
            assert migration is not None
            assert api("content", "/health/ready")[0] == 503
            assert api("gateway", "/health/ready")[0] == 503
            connection.execute(
                "INSERT INTO content.django_migrations (id,app,name,applied) VALUES (%s,%s,%s,%s)",
                migration)
        assert api("gateway", "/health/ready") == (200, {"status": "ok"})
        assert api("gateway", "/api/v1/videos")[0] == 200
        assert api("gateway", f"/api/v1/videos/{video_id}")[0] == 200
        assert api("gateway", f"/api/v1/videos/{uuid.uuid4()}")[0] == 404
        assert api("gateway", f"/api/v1/creators/{creator_id}")[0] == 200
        change_record(environments["content"], "UPDATE content.service_video SET state=%s WHERE id=%s",
                      ("draft", video_id))
        assert api("gateway", f"/api/v1/videos/{video_id}")[0] == 404
        assert api("gateway", "/api/v1/videos")[1]["items"] == []
        change_record(environments["content"], "UPDATE content.service_video SET state=%s WHERE id=%s",
                      ("published", video_id))
        change_record(environments["creators"],
                      "UPDATE creators.service_creatorprofile SET status=%s, restricted_at=now() WHERE id=%s",
                      ("restricted", creator_id))
        assert api("gateway", f"/api/v1/creators/{creator_id}")[0] == 404
        assert api("gateway", "/api/v1/auth/login", data={})[0] == 403
        assert api("identity", "/internal/auth/login", data={})[0] == 403
        assert api("content", "/videos")[0] == 403
        plaintext = HTTPConnection("127.0.0.1", ports["gateway"], timeout=3)
        try:
            plaintext.request("GET", "/health/live",
                              headers={"X-Forwarded-Proto": "https", "Host": "127.0.0.1"})
            status = plaintext.getresponse().status
            if status < 400:
                raise AssertionError("Forged proxy scheme bypassed staging TLS")
        except (ConnectionResetError, RemoteDisconnected):
            pass
        finally:
            plaintext.close()
        try:
            request(ports["gateway"], "/health/live", base / "admin-password", **host)
        except ssl.SSLError:
            pass
        else:
            raise AssertionError("Untrusted TLS CA was accepted")
        # Verify actual certificate hostname failure, not only origin syntax.
        context = ssl.create_default_context(cafile=str(certificate))
        with socket.create_connection(("127.0.0.1", ports["gateway"]), timeout=3) as sock:
            try:
                with context.wrap_socket(sock, server_hostname="wrong.example.test"):
                    raise AssertionError("Wrong-host TLS certificate was accepted")
            except ssl.SSLCertVerificationError:
                pass
        unsafe = json.loads(peers.read_text())
        unsafe["content"] = "http://127.0.0.1"
        secret_file(peers, json.dumps(unsafe))
        check_environment(environments["gateway"], "gateway", succeeds=False)
        secret_file(peers, json.dumps({name: f"https://127.0.0.1:{ports[name]}"
                                     for name in ("content", "creators", "identity")}))
        approvals = base / "account-approvals.json"
        secret_file(approvals, json.dumps({name: "disposable-test-approval"
                                          for name in ("identity", "smtp", "credentials", "transport")}))
        smtp_user, smtp_password = base / "smtp-user", base / "smtp-password"
        secret_file(smtp_user, "fixture@example.test")
        secret_file(smtp_password, secrets.token_urlsafe(48))
        for service in ("identity", "gateway"):
            stop(processes[service])
            environment = environments[service]
            environment.update(
                KOLOVIBE_STAGING_ACCOUNTS="1", KOLOVIBE_ACCOUNT_APPROVAL_FILE=str(approvals),
                KOLOVIBE_SMTP_HOST="test-only.invalid", KOLOVIBE_SMTP_PORT="587",
                KOLOVIBE_SMTP_USER_FILE=str(smtp_user), KOLOVIBE_SMTP_PASSWORD_FILE=str(smtp_password),
                KOLOVIBE_FROM_EMAIL="fixture@example.test")
            check_environment(environment, service)
            log = stack.enter_context((base / f"accounts-{service}.log").open("w"))
            process = subprocess.Popen(
                [sys.executable, "-m", "gunicorn", "--config",
                 str(ROOT / "services/staging_runtime/gunicorn.conf.py"),
                 "--bind", f"127.0.0.1:{ports[service]}", "--workers", "1",
                 "verify_staging_runtime:test_application()"],
                cwd=ROOT / "services" / service, env=environment, stdout=log, stderr=log)
            stack.callback(stop, process)
            processes[service] = process
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise AssertionError(f"Approved account fixture exited: {service}")
                try:
                    if api(service, "/health/live")[0] == 200:
                        break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise AssertionError("Approved account fixture startup timed out")
                time.sleep(0.1)
        account = {"email": "staging@example.test", "password": secrets.token_urlsafe(48),
                   "display_name": "Staging fixture"}
        assert api("gateway", "/api/v1/auth/register", data=account)[0] == 201
        code = (base / "verification-mail").read_text().split(": ", 1)[1]
        assert api("gateway", "/api/v1/auth/verify", data={"code": code})[0] == 200
        status, session = api("gateway", "/api/v1/auth/login",
                              data={key: account[key] for key in ("email", "password")})
        assert status == 200
        assert api("gateway", "/api/v1/me", token=session["access_token"])[0] == 200
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: api("gateway", "/api/v1/auth/refresh",
                                                    data={"refresh_token": session["refresh_token"]}),
                                      range(2)))
        assert sorted(status for status, _ in responses) == [200, 401]
        assert api("gateway", "/api/v1/me", token=session["access_token"])[0] == 401
        status, session = api("gateway", "/api/v1/auth/login",
                              data={key: account[key] for key in ("email", "password")})
        assert status == 200
        assert api("gateway", "/api/v1/auth/logout", data={}, token=session["access_token"])[0] == 204
        assert api("gateway", "/api/v1/me", token=session["access_token"])[0] == 401
        rotated = secrets.token_urlsafe(48)
        secret_file(callers, json.dumps({"gateway": rotated}))
        assert api("gateway", "/health/ready")[0] == 503
        secret_file(outbound, rotated)
        assert api("gateway", "/health/ready") == (200, {"status": "ok"})
        stop(processes["content"])
        assert api("gateway", "/health/ready")[0] == 503
        print("PASS: eight staging profiles, Gunicorn/TLS, readiness, route/secret gates, "
              "approved account mail/refresh/revocation, signing rotation and dependency outage", flush=True)


if __name__ == "__main__":
    verify()
