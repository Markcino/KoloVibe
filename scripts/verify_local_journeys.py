"""Real gateway journeys in task-owned TLS PostgreSQL and loopback HTTP fixtures."""

from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.cookies import SimpleCookie
import json
import os
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
    if service == "identity":
        from django.conf import settings
        # Disposable contract fixture only; password-strength/hash work is tested
        # by Identity's own suite. Keep real HTTP journeys within their timeouts.
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        settings.EMAIL_BACKEND = "verify_local_journeys.CapturedMail"
        settings.EMAIL_HOST = "test-only.invalid"
        settings.DEFAULT_FROM_EMAIL = "fixture@example.test"
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", f"127.0.0.1:{int(port)}",
                               "--noreload"])


def request(port, path, *, method="GET", data=None, headers=None, cookies=None, form=None):
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
        services = ("identity", "content", "creators", "gateway", "web")
        for service in services:
            sock = stack.enter_context(socket.socket())
            sock.bind(("127.0.0.1", 0))
            ports[service] = sock.getsockname()[1]
            reservations[service] = sock
        signing_key = secrets.token_urlsafe(48)
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
                environment["KOLOVIBE_GATEWAY_OUTBOUND_KEY"] = signing_key
                for peer in ("identity", "content", "creators"):
                    environment[f"KOLOVIBE_{peer.upper()}_URL"] = f"http://127.0.0.1:{ports[peer]}"
            elif service != "web":
                environment["KOLOVIBE_CALLER_GATEWAY_KEY"] = signing_key
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
                    status, _ = request(ports[service], "/" if service == "web" else "/health/live")
                    if status == 200:
                        break
                except (OSError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Disposable {service} readiness timed out")
                time.sleep(0.1)

        def api(path, *, data=None, token=None):
            status, raw = request(ports["gateway"], "/api/v1" + path,
                                  method="POST" if data is not None else "GET", data=data,
                                  headers={"Authorization": "Bearer " + token} if token else None)
            return status, json.loads(raw) if raw else None

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

            def test_web_reads_real_gateway_and_rejects_unprotected_posts(self):
                status, page = request(ports["web"], "/")
                self.assertEqual(status, 200)
                self.assertIn(b"Next page", page)
                status, _ = request(ports["web"], "/login/", method="POST",
                                    data={"email": "journey@example.test"})
                self.assertEqual(status, 403)

            def test_web_register_verify_login_account_and_logout(self):
                cookies = SimpleCookie()
                self.assertEqual(request(ports["web"], "/register/", cookies=cookies)[0], 200)
                password = secrets.token_urlsafe(24)

                def post(path, form):
                    return request(ports["web"], path, method="POST", cookies=cookies,
                                   form={"csrfmiddlewaretoken": cookies["csrftoken"].value, **form})

                self.assertEqual(post("/register/", {"email": "web-journey@example.test",
                    "display_name": "Web Fixture", "password": password})[0], 302)
                code = mailed_code(base)
                self.assertEqual(post("/verify/", {"email": "web-journey@example.test", "code": code})[0], 302)
                self.assertEqual(post("/login/", {"email": "web-journey@example.test",
                                                "password": password})[0], 302)
                self.assertTrue(cookies["kv_refresh"]["httponly"])
                status, page = request(ports["web"], "/account/", cookies=cookies)
                self.assertEqual(status, 200)
                self.assertIn(b"Web Fixture", page)
                self.assertNotIn(cookies["kv_refresh"].value.encode(), page)
                self.assertEqual(post("/logout/", {})[0], 302)
                self.assertNotIn("kv_refresh", cookies)
                self.assertEqual(request(ports["web"], "/account/", cookies=cookies)[0], 302)

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
