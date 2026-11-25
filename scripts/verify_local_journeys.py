"""Real gateway journeys in task-owned TLS PostgreSQL and loopback HTTP fixtures."""

from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.cookies import SimpleCookie
import json
import os
import re
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import unittest
import uuid
from urllib.parse import urlencode

from django.core.mail.backends.base import BaseEmailBackend
from jsonschema import Draft202012Validator, FormatChecker
import yaml

import business_journey
from smtp_fixture import mailed_code
from test_postgres_foundations import ROOT, postgres_fixture, secret_file


def fixture_directory():
    path = Path(os.environ["KOLOVIBE_PG_FIXTURE"])
    if (not path.name.startswith("kolovibe-pg-test-")
            or not (path / "data/postmaster.pid").is_file()):
        raise RuntimeError("Local journeys require the disposable PostgreSQL fixture")
    return path


class CapturedMail(BaseEmailBackend):
    def send_messages(self, messages):
        path = fixture_directory() / "verification-mail"
        count = 0
        for message in messages:
            secret_file(path, message.body)
            count += 1
        return count


def serve(service, port):
    fixture_directory()
    directory = ROOT / ("apps/web_django" if service == "web" else f"services/{service}")
    sys.path.insert(0, str(directory))
    os.environ["DJANGO_SETTINGS_MODULE"] = "web.settings" if service == "web" else "service.settings"
    import django
    django.setup()
    if service == "web":
        from django.conf import settings
        settings.DEBUG_PROPAGATE_EXCEPTIONS = True
        # Session tables belong only to this disposable fixture, never the developer's local DB.
        settings.DATABASES["default"]["NAME"] = fixture_directory() / "web-fixture.sqlite3"
        from django.core.management import call_command
        call_command("migrate", verbosity=0, interactive=False)
    if service == "identity":
        from django.conf import settings
        # Disposable contract fixture only; password-strength/hash work is tested
        # by Identity's own suite. Keep real HTTP journeys within their timeouts.
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        # Fixture-only opt-in after fixture_directory() proves the disposable PostgreSQL boundary.
        # Real local and staging application settings remain unchanged.
        settings.STAGING_PRIVILEGED = True
        settings.EMAIL_BACKEND = "verify_local_journeys.CapturedMail"
        settings.EMAIL_HOST = "test-only.invalid"
        settings.DEFAULT_FROM_EMAIL = "fixture@example.test"
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", f"127.0.0.1:{int(port)}",
                               "--noreload"])


def request(port, path, *, method="GET", data=None, headers=None, cookies=None, form=None, response_headers=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        body = None if data is None else json.dumps(data)
        fields = {"Content-Type": "application/json", **(headers or {})}
        if form is not None:
            body = urlencode(form)
            fields["Content-Type"] = "application/x-www-form-urlencoded"
        if cookies:
            fields["Cookie"] = "; ".join(f"{name}={morsel.value}" for name, morsel in cookies.items())
        connection.request(method, path, body=body, headers=fields)
        response = connection.getresponse()
        if response_headers is not None:
            response_headers.update(dict(response.getheaders()))
        if cookies is not None:
            for name, value in response.getheaders():
                if name.lower() == "set-cookie":
                    cookies.load(value)
            for name in list(cookies):
                if cookies[name]["max-age"] == "0":
                    del cookies[name]
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise AssertionError("Oversized local journey response")
        return response.status, raw
    finally:
        connection.close()


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def seed(environment, creator_id, video_ids):
    import psycopg
    from datetime import datetime, timezone
    with psycopg.connect(
        dbname=environment["KOLOVIBE_DB_NAME"], user=environment["KOLOVIBE_DB_USER"],
        host="127.0.0.1", port=environment["KOLOVIBE_DB_PORT"],
        password=Path(environment["KOLOVIBE_DB_PASSWORD_FILE"]).read_text(),
        sslmode="verify-full", sslrootcert=environment["KOLOVIBE_DB_SSLROOTCERT"],
    ) as connection:
        now = datetime.now(timezone.utc)
        if environment["KOLOVIBE_SERVICE_NAME"] == "creators":
            connection.execute(
                "INSERT INTO creators.service_creatorprofile "
                "(id,user_id,handle,bio,status,reviewed_at,created_at,display_name,location) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (creator_id, uuid.uuid4(), "fixture-creator", "", "active", now, now, "Fixture creator", ""))
        else:
            for ident in video_ids:
                connection.execute(
                    "INSERT INTO content.service_video "
                    "(id,creator_id,title,description,state,visibility,"
                    "provider_asset_id,moderation_approved_at,created_at,tags) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (ident, creator_id, "Fixture original", "", "published", "public",
                     str(uuid.uuid4()), now, now, "[]"))


def verify():
    spec = yaml.safe_load((ROOT / "docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml").read_text())

    def contract(path, method, status, payload):
        operation = spec["paths"][path][method]
        if operation.get("x-implementation") != "local":
            raise AssertionError("Journey attempted an unapproved contract")
        schema = operation["responses"][str(status)]["content"]["application/json"]["schema"]
        Draft202012Validator(
            {**schema, "components": spec["components"]},
            format_checker=FormatChecker(),
        ).validate(payload)

    with postgres_fixture() as (base, environments), ExitStack() as stack:
        ports = {}
        reservations = {}
        services = ("identity", "content", "creators", "moderation", "engagement", "points", "audit", "business", "gateway", "web")
        for service in services:
            sock = stack.enter_context(socket.socket())
            sock.bind(("127.0.0.1", 0))
            ports[service] = sock.getsockname()[1]
            reservations[service] = sock
        peer_keys = {service: secrets.token_urlsafe(48) for service in services if service not in {"gateway", "web"}}
        moderation_key = secrets.token_urlsafe(48)
        from cryptography.fernet import Fernet
        secret_file(base / "mfa-key", Fernet.generate_key().decode())
        environments["identity"]["KOLOVIBE_MFA_ENCRYPTION_KEY_FILE"] = str(base / "mfa-key")
        creator_id = uuid.uuid4()
        video_ids = [uuid.uuid4() for _ in range(21)]
        seed(environments["creators"], creator_id, video_ids)
        seed(environments["content"], creator_id, video_ids)
        environments["web"] = {
            **environments["gateway"], "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
            "KOLOVIBE_GATEWAY_URL": f"http://127.0.0.1:{ports['gateway']}",
        }
        for service in services:
            environment = dict(environments[service])
            if service == "gateway":
                environment["KOLOVIBE_LOCAL_MEDIA_ENABLED"] = "1"
                environment["KOLOVIBE_LOCAL_BUSINESS_ENABLED"] = "1"
                for peer, key in peer_keys.items():
                    environment[f"KOLOVIBE_{peer.upper()}_URL"] = f"http://127.0.0.1:{ports[peer]}"
                    environment[f"KOLOVIBE_GATEWAY_OUTBOUND_KEY_{peer.upper()}"] = key
            elif service != "web":
                environment["KOLOVIBE_CALLER_GATEWAY_KEY"] = peer_keys[service]
            if service in {"gateway", "content", "moderation"}:
                environment["KOLOVIBE_LOCAL_MODERATION_ENABLED"] = "1"
            if service in {"gateway", "engagement", "points"}:
                environment["KOLOVIBE_LOCAL_POINTS_ENABLED"] = "1"
            if service == "content":
                environment["KOLOVIBE_CALLER_MODERATION_KEY"] = moderation_key
            if service == "moderation":
                environment["KOLOVIBE_MODERATION_OUTBOUND_KEY_CONTENT"] = moderation_key
                environment["KOLOVIBE_CONTENT_URL"] = f"http://127.0.0.1:{ports['content']}"
            log = stack.enter_context((base / f"{service}.log").open("w"))
            reservations[service].close()
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--serve", service, str(ports[service])],
                env=environment, stdout=log, stderr=log)
            stack.callback(stop, process)
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Disposable {service} process exited before readiness")
                try:
                    status, _ = request(ports[service], "/health/live")
                    if status == 200:
                        break
                except (OSError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Disposable {service} readiness timed out")
                time.sleep(0.1)

        def api(path, *, data=None, token=None, key=None, method=None, headers=None):
            status, raw = request(ports["gateway"], "/api/v1" + path,
                                  method=method or ("POST" if data is not None else "GET"), data=data,
                                  headers=({"Authorization": "Bearer " + token} if token else {}) | ({"Idempotency-Key": key} if key else {})
                                  | (headers or {}))
            return status, json.loads(raw) if raw else None

        def fixture_connection(service):
            import psycopg
            env = environments[service]
            return psycopg.connect(dbname=env["KOLOVIBE_DB_NAME"], user=env["KOLOVIBE_DB_USER"],
                host="127.0.0.1", port=env["KOLOVIBE_DB_PORT"], password=Path(env["KOLOVIBE_DB_PASSWORD_FILE"]).read_text(),
                sslmode="verify-full", sslrootcert=env["KOLOVIBE_DB_SSLROOTCERT"])

        def privileged_fixture(role, suffix=""):
            label = role + suffix
            import pyotp
            body = {"email": "web-" + label + "@example.test", "display_name": "Privileged Fixture",
                    "password": secrets.token_urlsafe(24)}
            if api("/auth/register", data=body)[0] != 201 or api("/auth/verify", data={
                    "email": body["email"], "code": mailed_code(base)})[0] != 200:
                raise AssertionError("Disposable privileged account setup failed")
            with fixture_connection("identity") as connection:
                actor = connection.execute("UPDATE identity.service_account SET role=%s WHERE email=%s RETURNING id",
                                           (role, body["email"])).fetchone()[0]
            factor = pyotp.random_base32()
            secret_file(base / (label + "-factor"), factor)
            secret_file(base / (label + "-code"), pyotp.TOTP(factor).now())
            env = dict(environments["identity"], KOLOVIBE_ENROLLMENT_SECRET_FILE=str(base / (label + "-factor")),
                       KOLOVIBE_ENROLLMENT_CODE_FILE=str(base / (label + "-code")))
            # Invoke the existing enrollment command, changing only the disposable process's settings.
            code = ("import os,sys,django;os.environ['DJANGO_SETTINGS_MODULE']='service.settings';django.setup();"
                    "from django.conf import settings;settings.STAGING_PRIVILEGED=True;"
                    "from django.core.management import call_command;"
                    "call_command('enroll_privileged_mfa', account_id=sys.argv[1], recovery_file=sys.argv[2], approval_reference='disposable-WEB-ADM-fixture')")
            result = subprocess.run([sys.executable, "-c", code, str(actor), str(base / (label + "-recovery"))],
                cwd=ROOT / "services/identity", env=env, capture_output=True, timeout=20)
            if result.returncode:
                raise AssertionError("Disposable privileged enrollment failed")
            return actor, body, (base / (label + "-recovery")).read_text().splitlines()[0]

        class Journeys(unittest.TestCase):
            def test_approved_viewer_role_reconciliation_and_studio(self):
                """Reproduce historical drift only inside the disposable fixture."""
                import psycopg
                password = secrets.token_urlsafe(24)
                email = "approved-creator@example.test"
                self.assertEqual(api("/auth/register", data={"email": email,
                    "display_name": "Approved Creator", "password": password})[0], 201)
                self.assertEqual(api("/auth/verify", data={"email": email, "code": mailed_code(base)})[0], 200)
                status, stale = api("/auth/login", data={"email": email, "password": password})
                self.assertEqual(status, 200)
                actor = stale["user"]["id"]
                self.assertEqual(stale["user"]["roles"], ["viewer"])
                self.assertEqual(api("/creators/me", token=stale["access_token"])[0], 403)
                profile_id, reviewer = uuid.uuid4(), uuid.uuid4()
                env = environments["creators"]
                with psycopg.connect(dbname=env["KOLOVIBE_DB_NAME"], user=env["KOLOVIBE_DB_USER"],
                        host="127.0.0.1", port=env["KOLOVIBE_DB_PORT"],
                        password=Path(env["KOLOVIBE_DB_PASSWORD_FILE"]).read_text(),
                        sslmode="verify-full", sslrootcert=env["KOLOVIBE_DB_SSLROOTCERT"]) as connection:
                    connection.execute("INSERT INTO creators.service_creatorprofile "
                        "(id,user_id,handle,bio,status,reviewed_at,created_at,display_name,location) "
                        "VALUES (%s,%s,'approved_fixture','','active',now(),now(),'Approved Creator','')",
                        (profile_id, actor))
                    connection.execute("INSERT INTO creators.service_creatorapplication "
                        "(account_id,invited_by,invited_at,status,profile_id,attestation_version,"
                        "submitted_at,reviewed_by,reviewed_at) "
                        "VALUES (%s,%s,now(),'approved',%s,'DEC-004-pilot-v1',now(),%s,now())",
                        (actor, reviewer, profile_id, reviewer))
                status, body = api("/creators/me", token=stale["access_token"])
                self.assertEqual(status, 401, body)
                self.assertEqual(api("/auth/refresh", data={"refresh_token": stale["refresh_token"]})[0], 401)
                status, fresh = api("/auth/login", data={"email": email, "password": password})
                self.assertEqual(status, 200)
                self.assertEqual(fresh["user"]["roles"], ["creator"])
                status, profile = api("/creators/me", token=fresh["access_token"])
                self.assertEqual(status, 200, profile)
                self.assertEqual(profile["user_id"], actor)
                self.assertEqual(profile["id"], str(profile_id))
                self.assertEqual(api("/creators/me/upload-eligibility", token=fresh["access_token"]),
                                 (200, {"upload_eligible": True, "creator_id": str(profile_id)}))
                with psycopg.connect(dbname=env["KOLOVIBE_DB_NAME"], user=env["KOLOVIBE_DB_USER"],
                        host="127.0.0.1", port=env["KOLOVIBE_DB_PORT"],
                        password=Path(env["KOLOVIBE_DB_PASSWORD_FILE"]).read_text(),
                        sslmode="verify-full", sslrootcert=env["KOLOVIBE_DB_SSLROOTCERT"]) as connection:
                    connection.execute("UPDATE creators.service_creatorprofile SET status='restricted', "
                                       "restricted_at=now() WHERE id=%s", (profile_id,))
                self.assertEqual(api("/creators/me", token=fresh["access_token"])[0], 403)
                self.assertEqual(api("/creators/me/upload-eligibility", token=fresh["access_token"]),
                                 (200, {"upload_eligible": False, "creator_id": None}))

            def test_copyright_intake_takedown_counter_notice_and_strike_reversal(self):
                password = secrets.token_urlsafe(24)
                email = "copyright-creator@example.test"
                self.assertEqual(api("/auth/register", data={"email": email, "password": password, "display_name": "Copyright Fixture"})[0], 201)
                self.assertEqual(api("/auth/verify", data={"email": email, "code": mailed_code(base)})[0], 200)
                with fixture_connection("identity") as connection:
                    owner = connection.execute("UPDATE identity.service_account SET role='creator' WHERE email=%s RETURNING id", (email,)).fetchone()[0]
                creator, video = uuid.uuid4(), uuid.uuid4()
                with fixture_connection("creators") as connection:
                    connection.execute("INSERT INTO creators.service_creatorprofile (id,user_id,handle,bio,status,reviewed_at,created_at,display_name,location) VALUES (%s,%s,'copyright_fixture','','active',now(),now(),'Copyright Fixture','')", (creator, owner))
                with fixture_connection("content") as connection:
                    connection.execute("INSERT INTO content.service_video (id,creator_id,title,description,state,visibility,provider_asset_id,moderation_approved_at,published_at,created_at,tags) VALUES (%s,%s,'Rights fixture','','published','public','playback/copyright-fixture.mp4',now(),now(),now(),'[]'::jsonb)", (video, creator))
                status, owned = api("/auth/login", data={"email": email, "password": password})
                self.assertEqual(status, 200)
                token = owned["access_token"]

                def operator(role):
                    actor, body, recovery = privileged_fixture(role, "-copyright")
                    status, challenge = api("/auth/login", data={name: body[name] for name in ("email", "password")})
                    self.assertEqual(status, 202)
                    status, session = api("/auth/mfa/verify", data={"challenge_token": challenge["challenge_token"], "code": recovery})
                    self.assertEqual(status, 200)
                    return actor, session["access_token"]

                moderator, mod_token = operator("moderator")
                administrator, admin_token = operator("administrator")
                intake = {"video_id": str(video), "work_reference": "Synthetic original work", "details": "Rights concern with identified original work.", "authority_attested": True}
                status, report = api("/copyright/reports", data=intake, token=token, key="http-copyright-report-001")
                self.assertEqual(status, 201, report)
                contract("/copyright/reports", "post", status, report)
                self.assertEqual(api("/copyright/reports", data=intake, token=token, key="http-copyright-report-001")[0], 200)
                with fixture_connection("content") as connection:
                    self.assertEqual(connection.execute("SELECT rights_status FROM content.service_video WHERE id=%s", (video,)).fetchone()[0], "claimed")
                path = "/moderation/reports/" + report["id"] + "/decisions"
                decision = {"action": "remove", "reason": "Copyright takedown confirmed after evidence review."}
                self.assertEqual(api(path, data=decision, token=mod_token, key="http-copyright-remove-001")[0], 403)
                with fixture_connection("moderation") as connection:
                    connection.execute("INSERT INTO moderation.service_moderatorassignment (moderator_id,queue_scope,target_id,active) VALUES (%s,'reports',%s,true)", (moderator, report["id"]))
                for _ in range(2):
                    self.assertEqual(api(path, data=decision, token=mod_token, key="http-copyright-remove-001")[0], 200)
                status, count = api("/creators/me/copyright", token=token)
                self.assertEqual((status, count), (200, {"strike_count": 1}))
                contract("/creators/me/copyright", "get", status, count)
                counter = {"reason": "I contest the takedown and supply my rights evidence.", "accuracy_attested": True}
                self.assertEqual(api(f"/videos/{video_ids[1]}/counter-notices", data=counter, token=token, key="http-counter-foreign-001")[0], 404)
                status, appeal = api(f"/videos/{video}/counter-notices", data=counter, token=token, key="http-copyright-counter-001")
                self.assertEqual(status, 201, appeal)
                contract("/videos/{video_id}/counter-notices", "post", status, appeal)
                self.assertEqual(api(f"/videos/{video}/counter-notices", data=counter, token=token, key="http-copyright-counter-001")[0], 200)
                with fixture_connection("moderation") as connection:
                    connection.execute("INSERT INTO moderation.service_moderatorassignment (moderator_id,queue_scope,target_id,active) VALUES (%s,'appeals',%s,true)", (moderator, appeal["id"]))
                restore_path = "/moderation/appeals/" + appeal["id"] + "/decisions"
                restore = {"action": "restore", "reason": "Independent reviewer accepted the supplied rights evidence."}
                self.assertEqual(api(restore_path, data=restore, token=mod_token, key="http-copyright-restore-001")[0], 403)
                for _ in range(2):
                    self.assertEqual(api(restore_path, data=restore, token=admin_token, key="http-copyright-restore-001")[0], 200)
                self.assertEqual(api("/creators/me/copyright", token=token), (200, {"strike_count": 0}))
                with fixture_connection("content") as connection:
                    self.assertEqual(connection.execute("SELECT rights_status FROM content.service_video WHERE id=%s", (video,)).fetchone()[0], "restored")
                    self.assertEqual(connection.execute("SELECT count(*) FROM content.service_rightsevent WHERE video_id=%s", (video,)).fetchone()[0], 3)
                    # This case owns its seeded video; keep later discovery fixtures isolated.
                    connection.execute("UPDATE content.service_video SET deleted_at=now(), visibility='private' WHERE id=%s", (video,))

            def test_account_contract_and_revocation(self):
                password = secrets.token_urlsafe(24)
                body = {"email": "journey@example.test", "display_name": "Fixture Viewer",
                        "password": password}
                schema = spec["components"]["schemas"]["RegisterRequest"]
                Draft202012Validator(schema, format_checker=FormatChecker()).validate(body)
                status, payload = api("/auth/register", data=body)
                self.assertEqual(status, 201)
                contract("/auth/register", "post", status, payload)
                code = mailed_code(base)
                status, payload = api("/auth/verify", data={"email": body["email"], "code": code})
                self.assertEqual(status, 200)
                contract("/auth/verify", "post", status, payload)
                self.assertEqual(api("/auth/verify", data={"email": body["email"], "code": code})[0], 400)
                status, tokens = api("/auth/login", data={"email": body["email"], "password": password})
                self.assertEqual(status, 200)
                contract("/auth/login", "post", status, tokens)
                status, account = api("/me", token=tokens["access_token"])
                self.assertEqual(status, 200)
                contract("/me", "get", status, account)
                self.assertEqual(account["id"], tokens["user"]["id"])
                status, rotated = api("/auth/refresh", data={"refresh_token": tokens["refresh_token"]})
                self.assertEqual(status, 200)
                contract("/auth/refresh", "post", status, rotated)
                self.assertEqual(api("/auth/refresh", data={"refresh_token": tokens["refresh_token"]})[0], 401)
                self.assertEqual(api("/me", token=rotated["access_token"])[0], 401)
                status, tokens = api("/auth/login", data={"email": body["email"], "password": password})
                self.assertEqual(status, 200)
                self.assertEqual(api("/auth/logout", data={"refresh_token": tokens["refresh_token"]})[0], 204)
                self.assertEqual(api("/me", token=tokens["access_token"])[0], 401)

            def test_concurrent_refresh_has_one_winner_and_revokes_reuse(self):
                password = secrets.token_urlsafe(24)
                email = "concurrent@example.test"
                self.assertEqual(api("/auth/register", data={
                    "email": email, "display_name": "Concurrent Viewer", "password": password})[0], 201)
                code = mailed_code(base)
                self.assertEqual(api("/auth/verify", data={"email": email, "code": code})[0], 200)
                status, tokens = api("/auth/login", data={"email": email, "password": password})
                self.assertEqual(status, 200)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(api, "/auth/refresh",
                        data={"refresh_token": tokens["refresh_token"]}) for _ in range(2)]
                    results = [future.result() for future in futures]
                self.assertEqual(sorted(status for status, _ in results), [200, 401])
                winner = next(payload for status, payload in results if status == 200)
                self.assertEqual(api("/me", token=winner["access_token"])[0], 401)

            def test_public_discovery_contract_and_pagination(self):
                status, first = api("/videos")
                self.assertEqual(status, 200)
                contract("/videos", "get", status, first)
                self.assertEqual(len(first["items"]), 20)
                status, second = api("/videos?cursor=" + first["next_cursor"])
                self.assertEqual(status, 200)
                contract("/videos", "get", status, second)
                ids = [item["id"] for item in first["items"] + second["items"]]
                self.assertEqual(set(ids), {str(ident) for ident in video_ids})
                self.assertEqual(len(ids), 21)
                self.assertIsNone(second["next_cursor"])
                status, video = api("/videos/" + ids[0])
                self.assertEqual(status, 200)
                contract("/videos/{video_id}", "get", status, video)
                status, creator = api("/creators/" + str(creator_id))
                self.assertEqual(status, 200)
                contract("/creators/{creator_id}", "get", status, creator)
                self.assertNotIn("user_id", creator)
                status, found = api("/creators/search?q=" + creator["handle"][:3])
                self.assertEqual(status, 200)
                contract("/creators/search", "get", status, found)
                self.assertIn(str(creator_id), [item["id"] for item in found["items"]])
                self.assertTrue(all("user_id" not in item for item in found["items"]))
                self.assertEqual(api("/videos/" + str(uuid.uuid4()))[0], 404)
                self.assertEqual(api("/videos?cursor=" + str(uuid.uuid4()))[0], 400)
                self.assertEqual(api("/creators/" + str(uuid.uuid4()))[0], 404)

            def test_unsigned_internal_requests_are_denied(self):
                for service in ("identity", "content", "creators"):
                    self.assertEqual(request(ports[service], "/internal/probe")[0], 403)
                self.assertEqual(api("/me")[0], 401)

            def test_WEB_ADM_002_real_privileged_console_and_owning_services(self):
                """Real HTTP, MFA, scoped reads, decision replay, and immutable audit evidence."""
                from html.parser import HTMLParser
                class Intent(HTMLParser):
                    value = None
                    def handle_starttag(self, tag, attrs):
                        values = dict(attrs)
                        if tag == "input" and values.get("name") == "intent":
                            self.value = values.get("value")

                for role in ("administrator", "moderator"):
                    actor, body, recovery = privileged_fixture(role)
                    if role == "administrator":
                        with fixture_connection("audit") as connection:
                            connection.execute("INSERT INTO audit.service_auditreadgrant (administrator_id,producer,active) VALUES (%s,'moderation',true)", (actor,))
                        with fixture_connection("points") as connection:
                            connection.execute("INSERT INTO points.points_entries (entry_id,creator_user_id,source_decision_id,delta,entry_type,rule_version,reason_code,created_at) VALUES (%s,%s,%s,1,'AWARD','fixture-v1','QUALIFIED_VIEW',now())", (uuid.uuid4(), actor, uuid.uuid4()))
                    else:
                        with fixture_connection("moderation") as connection:
                            connection.execute("INSERT INTO moderation.service_moderatorassignment (moderator_id,queue_scope,target_id,active) VALUES (%s,'videos',%s,true)", (actor, video_ids[0]))
                        with fixture_connection("engagement") as connection:
                            connection.execute("INSERT INTO engagement.service_fraudhold (id,account_id,video_id,reason_code,active,created_at) VALUES (%s,%s,%s,'FIXTURE_REVIEW',true,now())", (uuid.uuid4(), uuid.uuid4(), video_ids[0]))
                    cookies = SimpleCookie()
                    self.assertEqual(request(ports["web"], "/login/", cookies=cookies)[0], 200)
                    def post(path, form):
                        return request(ports["web"], path, method="POST", cookies=cookies,
                            form={"csrfmiddlewaretoken": cookies["csrftoken"].value, **form})
                    self.assertEqual(post("/login/", {"email": body["email"], "password": body["password"]})[0], 302)
                    self.assertEqual(request(ports["web"], "/admin/", cookies=cookies)[0], 302)
                    self.assertEqual(post("/login/mfa/", {"code": recovery})[0], 302)
                    self.assertTrue(cookies["sessionid"]["httponly"])
                    self.assertNotIn("kv_access", cookies)
                    self.assertNotIn("kv_refresh", cookies)
                    headers = {}
                    status, page = request(ports["web"], "/admin/", cookies=cookies, response_headers=headers)
                    self.assertEqual(status, 200)
                    self.assertIn(b"Dashboard", page)
                    self.assertIn("no-store", headers["Cache-Control"])
                    self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
                    # Validate live owning-service projections against the approved OpenAPI schemas.
                    status, challenged = api("/auth/login", data={key: body[key] for key in ("email", "password")})
                    self.assertEqual(status, 202)
                    second_code = (base / (role + "-recovery")).read_text().splitlines()[1]
                    status, tokens = api("/auth/mfa/verify", data={"challenge_token": challenged["challenge_token"], "code": second_code})
                    self.assertEqual(status, 200)
                    for live_path, schema_path in (("/moderation/totals", "/moderation/totals"),
                            ("/engagement/fraud-holds", "/engagement/fraud-holds"),
                            (f"/moderation/videos/{video_ids[0]}", "/moderation/videos/{video_id}"),
                            ("/admin/audit", "/admin/audit")):
                        status, payload = api(live_path, token=tokens["access_token"])
                        self.assertEqual(status, 200)
                        contract(schema_path, "get", status, payload)
                    if role == "administrator":
                        for live_path, schema_path in (("/admin/points/balances", "/admin/points/balances"),
                                (f"/admin/points/accounts/{actor}", "/admin/points/accounts/{account_id}")):
                            status, payload = api(live_path, token=tokens["access_token"])
                            self.assertEqual(status, 200)
                            contract(schema_path, "get", status, payload)
                    else:
                        self.assertEqual(api("/admin/points/balances", token=tokens["access_token"])[0], 403)
                    self.assertEqual(api("/auth/logout", data={"refresh_token": tokens["refresh_token"]})[0], 204)
                    status, page = request(ports["web"], "/admin/moderation/videos/?status=published", cookies=cookies)
                    self.assertEqual(status, 200)
                    self.assertEqual(request(ports["web"], f"/admin/moderation/videos/{video_ids[0]}/", cookies=cookies)[0], 200)
                    self.assertEqual(request(ports["web"], "/admin/audit/", cookies=cookies)[0], 200)
                    self.assertEqual(request(ports["web"], "/admin/points/", cookies=cookies)[0], 200 if role == "administrator" else 403)
                    if role == "moderator":
                        self.assertEqual(request(ports["web"], "/admin/moderation/reports/", cookies=cookies)[0], 403)
                        self.assertEqual(request(ports["web"], f"/admin/moderation/videos/{video_ids[1]}/", cookies=cookies)[0], 403)
                        with fixture_connection("moderation") as connection:
                            self.assertGreater(connection.execute("SELECT count(*) FROM moderation.moderation_audit_event WHERE actor_id=%s AND kind='moderation.assignment_denied'", (actor,)).fetchone()[0], 0)
                    else:
                        report_id = uuid.uuid4()
                        with fixture_connection("moderation") as connection:
                            connection.execute("INSERT INTO moderation.service_report (id,video_id,reporter_id,reason,details,status,created_at) VALUES (%s,%s,%s,'other','<script>fixture</script>','open',now())", (report_id, video_ids[0], uuid.uuid4()))
                        path = f"/admin/moderation/reports/{report_id}/"
                        status, page = request(ports["web"], path, cookies=cookies)
                        self.assertEqual(status, 200)
                        self.assertIn(b"&lt;script&gt;fixture&lt;/script&gt;", page)
                        parser = Intent()
                        parser.feed(page.decode())
                        self.assertTrue(parser.value)
                        decision = {"intent": parser.value, "action": "dismiss", "reason": "Reviewed disposable fixture evidence."}
                        self.assertEqual(request(ports["web"], path, method="POST", cookies=cookies, form=decision)[0], 403)
                        for _ in range(2):
                            self.assertEqual(post(path, decision)[0], 200)
                        with fixture_connection("moderation") as connection:
                            self.assertEqual(connection.execute("SELECT count(*) FROM moderation.service_moderationaction WHERE report_id=%s", (report_id,)).fetchone()[0], 1)
                            self.assertEqual(connection.execute("SELECT count(*) FROM moderation.moderation_audit_event WHERE actor_id=%s AND kind='moderation.decision_recorded'", (actor,)).fetchone()[0], 1)
                    self.assertEqual(post("/admin/logout/", {})[0], 302)
                    self.assertNotIn("sessionid", cookies)
                    self.assertEqual(request(ports["web"], "/admin/", cookies=cookies)[0], 302)

            def test_WEB_ADM_moderator_invitation_enrollment_and_concurrent_acceptance(self):
                """Real administrator UI, SMTP capture, encrypted setup, and PostgreSQL grant race."""
                import pyotp
                actor, administrator, recovery = privileged_fixture("administrator", "-invitations")
                cookies = SimpleCookie()
                self.assertEqual(request(ports["web"], "/login/", cookies=cookies)[0], 200)
                def form(path, fields, jar=cookies):
                    return request(ports["web"], path, method="POST", cookies=jar,
                        form={"csrfmiddlewaretoken": jar["csrftoken"].value, **fields})
                self.assertEqual(form("/login/", {k: administrator[k] for k in ("email", "password")})[0], 302)
                self.assertEqual(form("/login/mfa/", {"code": recovery})[0], 302)
                status, page = request(ports["web"], "/admin/team/", cookies=cookies)
                self.assertEqual(status, 200)
                proof = re.search(rb'name="intent" value="([^"]+)"', page).group(1).decode()
                email = "invited-reviewer@example.test"
                password = secrets.token_urlsafe(32)
                self.assertEqual(form("/admin/team/", {"operation": "create", "intent": proof,
                    "email": email, "display_name": "Invited reviewer", "reason": "Disposable invitation journey"})[0], 302)
                token = re.search(r"\n([A-Za-z0-9_-]{64})\n", (base / "verification-mail").read_text()).group(1)
                self.assertNotIn(token.encode(), request(ports["web"], "/admin/team/", cookies=cookies)[1])
                invitee = SimpleCookie()
                self.assertEqual(request(ports["web"], "/moderator-invitation/", cookies=invitee)[0], 200)
                self.assertEqual(form("/moderator-invitation/", {"email": email, "invitation_code": token,
                    "password": password}, invitee)[0], 302)
                status, page = request(ports["web"], "/moderator-invitation/", cookies=invitee)
                self.assertEqual(status, 200)
                # The web no longer exposes the authenticator seed in HTML.
                # Exercise its session-protected QR endpoint over real HTTP.
                self.assertIn(b'/moderator-invitation/qr/', page)
                self.assertNotIn(b'class="invitation-secret"', page)
                self.assertEqual(request(ports["web"], "/moderator-invitation/qr/")[0], 404)
                qr_headers = {}
                status, qr = request(ports["web"], "/moderator-invitation/qr/",
                                     cookies=invitee, response_headers=qr_headers)
                self.assertEqual(status, 200)
                self.assertTrue(qr.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(qr_headers["Content-Type"], "image/png")
                self.assertIn("no-store", qr_headers["Cache-Control"])
                # Read the disposable Identity fixture's encrypted pending seed
                # only inside this test; real clients must scan the QR code.
                from cryptography.fernet import Fernet
                with fixture_connection("identity") as connection:
                    self.assertIsNone(connection.execute("SELECT id FROM identity.service_account WHERE email=%s", (email,)).fetchone())
                    encrypted = connection.execute(
                        "SELECT encrypted_secret FROM identity.service_moderatorinvitation WHERE email=%s AND closed=false",
                        (email,)).fetchone()[0]
                secret = Fernet((base / "mfa-key").read_bytes().strip()).decrypt(encrypted.encode()).decode()
                self.assertRegex(secret, r"^[A-Z2-7]{32}$")
                # Keep enough of the current period for a real HTTP round trip.
                if time.time() % 30 > 25:
                    time.sleep(30 - time.time() % 30 + 0.1)
                status, page = form("/moderator-invitation/", {"code": pyotp.TOTP(secret).now()}, invitee)
                self.assertEqual(status, 200)
                self.assertIn(b"Your moderator account is ready", page)
                self.assertNotIn(b"recovery_codes", request(ports["web"], "/moderator-invitation/", cookies=invitee)[1])
                self.assertEqual(api("/auth/login", data={"email": email, "password": password})[0], 202)
                with fixture_connection("identity") as connection:
                    self.assertEqual(connection.execute("SELECT role,is_active FROM identity.service_account WHERE email=%s", (email,)).fetchone(), ("moderator", True))
                status, challenge = api("/auth/login", data={k: administrator[k] for k in ("email", "password")})
                self.assertEqual(status, 202)
                second_recovery = (base / "administrator-invitations-recovery").read_text().splitlines()[1]
                status, session = api("/auth/mfa/verify", data={"challenge_token": challenge["challenge_token"], "code": second_recovery})
                self.assertEqual(status, 200)
                access = session["access_token"]
                status, receipt = api("/admin/moderator-invitations", token=access, key=secrets.token_urlsafe(32),
                    data={"email": "concurrent-reviewer@example.test", "display_name": "Concurrent reviewer", "reason": "Disposable race fixture"})
                self.assertEqual(status, 202)
                contract("/admin/moderator-invitations", "post", status, receipt)
                code = re.search(r"\n([A-Za-z0-9_-]{64})\n", (base / "verification-mail").read_text()).group(1)
                payload = {"email": "concurrent-reviewer@example.test", "invitation_code": code}
                status, setup = api("/auth/moderator-invitations/setup", data={**payload, "password": secrets.token_urlsafe(32)})
                self.assertEqual(status, 200)
                contract("/auth/moderator-invitations/setup", "post", status, setup)
                if time.time() % 30 > 25:
                    time.sleep(30 - time.time() % 30 + 0.1)
                submitted = {**payload, "code": pyotp.TOTP(setup["secret"]).now()}
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: api("/auth/moderator-invitations/complete", data=submitted), range(2)))
                self.assertEqual(sorted(result[0] for result in results), [200, 401])
                contract("/auth/moderator-invitations/complete", "post", 200, next(result[1] for result in results if result[0] == 200))
                with fixture_connection("identity") as connection:
                    self.assertEqual(connection.execute("SELECT count(*) FROM identity.service_account WHERE email=%s", (payload["email"],)).fetchone()[0], 1)
                    self.assertEqual(connection.execute("SELECT count(*) FROM identity.service_moderatorinvitationevent e JOIN identity.service_securityevent s ON s.id=e.event_id WHERE e.invitation_id=%s AND s.kind='moderator.invitation_accepted'", (receipt["id"],)).fetchone()[0], 1)

            def test_business_end_to_end_journey(self):
                """Phase 6E: sign-in to verification, discovery, inquiry, review, report, staff and revocation over real HTTP."""
                from types import SimpleNamespace
                business_journey.run(self, SimpleNamespace(
                    api=api, request=request, contract=contract, ports=ports, base=base,
                    privileged_fixture=privileged_fixture, fixture_connection=fixture_connection))

            def test_web_admin_boundary_and_csrf(self):
                self.assertEqual(request(ports["web"], "/")[0], 302)
                for path in ("/register/", "/verify/", "/account/", "/creator/", "/points/",
                             f"/videos/{video_ids[0]}/", f"/creators/{creator_id}/"):
                    self.assertEqual(request(ports["web"], path)[0], 404)
                for path in ("/admin/", "/admin/moderation/videos/", "/admin/moderation/reports/",
                             "/admin/moderation/appeals/", "/admin/points/", "/admin/audit/", "/admin/account/"):
                    self.assertEqual(request(ports["web"], path)[0], 302)
                status, _ = request(ports["web"], "/login/", method="POST",
                                    data={"email": "journey@example.test"})
                self.assertEqual(status, 403)

            def test_web_rejects_real_viewer_login_without_browser_credentials(self):
                body = {"email": "web-journey@example.test", "display_name": "Web Fixture",
                        "password": secrets.token_urlsafe(24)}
                self.assertEqual(api("/auth/register", data=body)[0], 201)
                self.assertEqual(api("/auth/verify", data={"email": body["email"],
                                                         "code": mailed_code(base)})[0], 200)
                cookies = SimpleCookie()
                self.assertEqual(request(ports["web"], "/login/", cookies=cookies)[0], 200)
                status, page = request(ports["web"], "/login/", method="POST", cookies=cookies,
                    form={"csrfmiddlewaretoken": cookies["csrftoken"].value,
                          "email": body["email"], "password": body["password"]})
                self.assertEqual(status, 403)
                self.assertNotIn(body["email"].encode(), page)
                self.assertNotIn("kv_access", cookies)
                self.assertNotIn("kv_refresh", cookies)
                self.assertNotIn("sessionid", cookies)
                self.assertEqual(request(ports["web"], "/admin/", cookies=cookies)[0], 302)

        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Journeys))
        if not result.wasSuccessful():
            # Disposable fixture credentials are synthetic; print only the web
            # traceback tail to locate an unexpected 500, not full request logs.
            tail = (base / "web.log").read_text().splitlines()[-35:]
            print("\n".join(tail), file=sys.stderr)
            raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--serve":
        serve(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 1:
        verify()
    else:
        raise SystemExit("Usage: verify_local_journeys.py [--serve SERVICE PORT]")
