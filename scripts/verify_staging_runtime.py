"""Restricted staging acceptance in disposable PostgreSQL, TLS and mail fixtures."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.client import HTTPConnection, HTTPSConnection, RemoteDisconnected
import hashlib
import hmac
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
    if settings.KOLOVIBE_SERVICE_NAME == "identity" and not os.getenv("KOLOVIBE_SMTP_FIXTURE"):
        settings.EMAIL_BACKEND = "verify_local_journeys.CapturedMail"
    return application


def request(port, path, ca, *, data=None, token=None, host=None, headers=None):
    context = ssl.create_default_context(cafile=str(ca))
    connection = HTTPSConnection("localhost", port, context=context, timeout=8)
    try:
        sent = {"Content-Type": "application/json", **(headers or {})}
        if token:
            sent["Authorization"] = "Bearer " + token
        if host:
            sent["Host"] = host
        connection.request("POST" if data is not None else "GET", path,
                           body=None if data is None else json.dumps(data), headers=sent)
        response = connection.getresponse()
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise AssertionError("Oversized staging response")
        content = (json.loads(raw) if raw and response.getheader("Content-Type", "").startswith(
            "application/json") else raw)
        return response.status, content if raw else None
    finally:
        connection.close()


def sign_headers(caller, audience, key, path="/internal/probe", *, nonce=None, stamp=None):
    """Headers a service holding `key` would send; used to prove what each credential can and cannot do."""
    nonce, stamp = nonce or secrets.token_urlsafe(24), stamp or str(int(time.time()))
    canonical = "\n".join((caller, audience, stamp, nonce, "GET", path, hashlib.sha256(b"").hexdigest()))
    return {"X-KoloVibe-Caller": caller, "X-KoloVibe-Timestamp": stamp, "X-KoloVibe-Nonce": nonce,
            "X-KoloVibe-Signature": hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()}


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
    launch = subprocess.run(
        [sys.executable, "-m", "staging_runtime.launch", "--check-settings"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=20)
    if (launch.returncode == 0) != succeeds:
        raise AssertionError(f"Shared-image launcher staging profile mismatch: {service}")


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
        # One independent gateway credential per peer: the gateway holds the map, and each
        # receiver holds only the entry meant for it. Services that never receive gateway
        # calls hold no gateway credential at all.
        gateway_keys = {peer: secrets.token_urlsafe(48) for peer in ("content", "creators", "identity")}
        probe = secrets.token_urlsafe(48)
        callers = {service: base / f"{service}-callers.json" for service in SERVICES}
        outbound = base / "outbound"
        probe_path = base / "probe"
        peers = base / "peers.json"
        for service in SERVICES:
            secret_file(callers[service], json.dumps(
                {"gateway": gateway_keys[service]} if service in gateway_keys else {}))
        secret_file(outbound, json.dumps(gateway_keys))
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
                KOLOVIBE_CALLER_KEYS_FILE=str(callers[service]), KOLOVIBE_PROBE_TOKEN_FILE=str(probe_path),
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
                 "--bind", f"127.0.0.1:{ports[service]}", "--workers",
                 "2" if service == "identity" else "1",
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
        held = [json.loads(callers[peer].read_text())["gateway"] for peer in gateway_keys]
        assert len(set(held)) == len(gateway_keys), "Receivers share one gateway credential"
        for audience, key in gateway_keys.items():
            def probe_as(caller, signing_key, *, signed_for=audience, nonce=None):
                return api(audience, "/internal/probe", headers=sign_headers(
                    caller, signed_for, signing_key, nonce=nonce))[0]
            assert probe_as("gateway", key) == 200, audience
            for other, other_key in gateway_keys.items():
                if other != audience:
                    assert probe_as("gateway", other_key) == 403, "Another peer's credential was accepted"
                    assert probe_as("gateway", key, signed_for=other) == 403
            nonce = secrets.token_urlsafe(24)
            assert probe_as("gateway", key, nonce=nonce) == 200
            assert probe_as("gateway", key, nonce=nonce) == 403, "Replayed nonce was accepted"
            assert probe_as("gateway", key[:-1] + ("A" if key[-1] != "A" else "B")) == 403
            assert probe_as("content" if audience != "content" else "creators", key) == 403
        for audience in set(SERVICES) - set(gateway_keys):
            for key in gateway_keys.values():
                status = api(audience, "/internal/probe", headers=sign_headers("gateway", audience, key))[0]
                assert status == 403, f"A gateway credential was accepted by {audience}"
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
        from smtp_fixture import smtp_fixture
        smtp_port = stack.enter_context(smtp_fixture(base))
        for service in ("identity", "gateway"):
            stop(processes[service])
            environment = environments[service]
            environment.update(
                KOLOVIBE_STAGING_ACCOUNTS="1", KOLOVIBE_ACCOUNT_APPROVAL_FILE=str(approvals),
                KOLOVIBE_SMTP_HOST="127.0.0.1", KOLOVIBE_SMTP_PORT=str(smtp_port),
                KOLOVIBE_SMTP_CA_FILE=str(certificate), KOLOVIBE_SMTP_FIXTURE="1",
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
        accepted = {kind: api("gateway", f"/api/v1/legal/{kind}")[1]["version"] for kind in ("terms", "privacy")}
        account = {"email": "staging@example.test", "password": secrets.token_urlsafe(48),
                   "display_name": "Staging fixture", "accepted": accepted}
        assert api("gateway", "/api/v1/auth/register", data=account)[0] == 201
        from smtp_fixture import mailed_code
        code = mailed_code(base)
        assert api("gateway", "/api/v1/auth/verify", data={"email": account["email"], "code": code})[0] == 200
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

        from cryptography.fernet import Fernet
        import pyotp
        encryption_file = base / "mfa-encryption"
        secret_file(encryption_file, Fernet.generate_key().decode())
        factor_secret = pyotp.random_base32()
        factor_file, code_file = base / "factor-secret", base / "factor-code"
        secret_file(factor_file, factor_secret)
        secret_file(code_file, pyotp.TOTP(factor_secret).now())
        identity_peers = base / "identity-audit-peers"
        secret_file(identity_peers, json.dumps({"audit": f"https://127.0.0.1:{ports['audit']}"}))
        identity_signing = secrets.token_urlsafe(48)
        identity_outbound = base / "identity-outbound"
        secret_file(identity_outbound, identity_signing)
        secret_file(callers["audit"], json.dumps({"identity": identity_signing}))
        secret_file(approvals, json.dumps({name: "disposable-test-approval"
                                          for name in ("identity", "smtp", "credentials",
                                                       "transport", "mfa", "audit")}))
        environments["identity"].update(
            KOLOVIBE_MFA_ENCRYPTION_KEY_FILE=str(encryption_file),
            KOLOVIBE_TRUSTED_PEERS_FILE=str(identity_peers),
            KOLOVIBE_OUTBOUND_KEY_FILE=str(identity_outbound))
        def restart_service(service):
            environment = environments[service]
            check_environment(environment, service)
            stop(processes[service])
            log = stack.enter_context((base / f"privileged-{service}.log").open("w"))
            process = subprocess.Popen(
                [sys.executable, "-m", "gunicorn", "--config",
                 str(ROOT / "services/staging_runtime/gunicorn.conf.py"),
                 "--bind", f"127.0.0.1:{ports[service]}", "--workers",
                 "2" if service == "identity" else "1",
                 "verify_staging_runtime:test_application()"],
                cwd=ROOT / "services" / service, env=environment, stdout=log, stderr=log)
            stack.callback(stop, process)
            processes[service] = process
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise AssertionError("Privileged fixture process failed")
                try:
                    if api(service, "/health/live")[0] == 200:
                        break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise AssertionError("Privileged fixture startup timed out")
                time.sleep(0.1)
        for service in ("identity", "gateway"):
            environments[service]["KOLOVIBE_STAGING_PRIVILEGED"] = "1"
            restart_service(service)

        from validate_identity_secrets import SECRET_FILES, CONFIG_FILES
        protected_environment = dict(environments["identity"])
        protected_environment.update({
            source: Path(environments["identity"][target]).read_text()
            for source, target in {**SECRET_FILES, **CONFIG_FILES}.items()})
        offline = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_identity_secrets.py")],
            env=protected_environment, capture_output=True, text=True, timeout=40)
        if offline.returncode:
            raise AssertionError("Complete protected identity secret validation failed")
        with admin_connection(base, environments["identity"]) as connection:
            privileged_id = connection.execute(
                "UPDATE identity.service_account SET role=%s WHERE email=%s RETURNING id",
                ("moderator", account["email"])).fetchone()[0]
        enroll_environment = dict(
            environments["identity"], KOLOVIBE_ENROLLMENT_SECRET_FILE=str(factor_file),
            KOLOVIBE_ENROLLMENT_CODE_FILE=str(code_file))
        secret_file(code_file, pyotp.TOTP(factor_secret).now())
        enrolled = subprocess.run(
            [sys.executable, "manage.py", "enroll_privileged_mfa",
             "--account-id", str(privileged_id), "--recovery-file", str(base / "recovery-codes"),
             "--approval-reference", "disposable-owner-approval"],
            cwd=ROOT / "services/identity", env=enroll_environment,
            capture_output=True, text=True, timeout=20)
        if enrolled.returncode:
            raise AssertionError("Disposable privileged enrollment failed")
        status, challenged = api("gateway", "/api/v1/auth/login",
                                 data={key: account[key] for key in ("email", "password")})
        assert status == 202 and "access_token" not in challenged
        recovery = (base / "recovery-codes").read_text().splitlines()[0]
        status, privileged = api("gateway", "/api/v1/auth/mfa/verify",
                                 data={"challenge_token": challenged["challenge_token"], "code": recovery})
        assert status == 200
        assert api("gateway", "/api/v1/me", token=privileged["access_token"])[0] == 200
        assert api("gateway", "/api/v1/auth/mfa/verify",
                   data={"challenge_token": challenged["challenge_token"], "code": recovery})[0] == 401
        status, challenged = api("gateway", "/api/v1/auth/login",
                                 data={key: account[key] for key in ("email", "password")})
        assert status == 202
        assert api("gateway", "/api/v1/auth/mfa/verify",
                   data={"challenge_token": challenged["challenge_token"], "code": recovery})[0] == 401
        # Enrollment consumed its period. Future codes must fail until their
        # actual boundary; then exercise concurrent consumption of a current code.
        next_period = (int(time.time()) // 30 + 1) * 30
        assert api("gateway", "/api/v1/auth/mfa/verify",
                   data={"challenge_token": challenged["challenge_token"],
                         "code": pyotp.TOTP(factor_secret).at(next_period)})[0] == 401
        time.sleep(max(0, next_period - time.time()) + 0.1)
        code = pyotp.TOTP(factor_secret).now()
        def verify_concurrently(_):
            return api("gateway", "/api/v1/auth/mfa/verify",
                       data={"challenge_token": challenged["challenge_token"], "code": code})[0]
        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(verify_concurrently, range(2))) == [200, 401]

        stop(processes["audit"])
        failed_delivery = subprocess.run(
            [sys.executable, "manage.py", "deliver_security_audit", "--limit", "1"],
            cwd=ROOT / "services/identity", env=environments["identity"],
            capture_output=True, text=True, timeout=20)
        assert failed_delivery.returncode != 0
        with admin_connection(base, environments["identity"]) as connection:
            assert connection.execute(
                "SELECT count(*) FROM identity.service_auditdelivery "
                "WHERE delivered_at IS NULL AND attempts > 0"
            ).fetchone()[0] > 0
        restart_service("audit")
        delivery = subprocess.run(
            [sys.executable, "manage.py", "deliver_security_audit"],
            cwd=ROOT / "services/identity", env=environments["identity"],
            capture_output=True, text=True, timeout=60)
        if delivery.returncode:
            raise AssertionError("Real signed TLS audit delivery failed")
        with admin_connection(base, environments["identity"]) as connection:
            assert connection.execute(
                "SELECT count(*) FROM identity.service_auditdelivery WHERE delivered_at IS NULL"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM audit.service_securityevent WHERE kind=%s",
                ("mfa.recovery_used",)).fetchone()[0] == 1
            import psycopg
            from psycopg import sql
            for schema in ("identity", "audit"):
                table = sql.Identifier(schema, "service_securityevent")
                for statement in (
                        sql.SQL("DELETE FROM {}").format(table),
                        sql.SQL("UPDATE {} SET kind='login.failed'").format(table),
                        sql.SQL("TRUNCATE {} CASCADE").format(table)):
                    try:
                        connection.execute(statement)
                    except psycopg.errors.RaiseException:
                        pass
                    else:
                        raise AssertionError("PostgreSQL permitted security evidence mutation")
        # Rotate only the gateway-to-content credential, with an overlap so there is no outage.
        rotated = secrets.token_urlsafe(48)
        previous = dict(gateway_keys)
        secret_file(callers["content"], json.dumps({"gateway": [rotated, previous["content"]]}))
        assert api("gateway", "/health/ready") == (200, {"status": "ok"})
        secret_file(outbound, json.dumps({**previous, "content": rotated}))
        assert api("gateway", "/health/ready") == (200, {"status": "ok"})
        secret_file(callers["content"], json.dumps({"gateway": rotated}))
        assert api("gateway", "/health/ready") == (200, {"status": "ok"})
        assert api("content", "/internal/probe", headers=sign_headers(
            "gateway", "content", previous["content"]))[0] == 403, "Retired credential still accepted"
        assert api("creators", "/internal/probe", headers=sign_headers(
            "gateway", "creators", previous["creators"]))[0] == 200, "Rotation disturbed another peer"
        secret_file(outbound, json.dumps(previous))
        assert api("gateway", "/health/ready")[0] == 503
        secret_file(outbound, json.dumps({**previous, "content": rotated}))
        assert api("gateway", "/health/ready") == (200, {"status": "ok"})
        stop(processes["content"])
        assert api("gateway", "/health/ready")[0] == 503
        print("PASS: eight staging profiles, Gunicorn/TLS, readiness, route/secret gates, "
              "loopback SMTP STARTTLS, protected secret validation, concurrent privileged MFA, "
              "signed audit outage/retry and append-only SQL, account refresh/revocation, "
              "signing rotation and dependency outage", flush=True)


if __name__ == "__main__":
    verify()
