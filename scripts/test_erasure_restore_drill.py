"""Mandate 3.4 restore drill on a disposable, TLS-only PostgreSQL: after an older Identity backup is restored, erased
data does not return.

1. Identity: a person signs in and asks for deletion; an administrator starts the review. pg_dump backs up the
   identity schema (the "older backup").
2. Identity: the deletion is approved and every service confirms, so the erasure completes. Identity's own
   deliver_security_audit command hands its events on; Audit's own ingest view stores them in the audit schema.
3. pg_restore puts the older identity schema back. The drill checks the person really is back (active, signed in,
   original email), which is the problem 3.4 exists to fix.
4. Audit's erasure-recovery view answers what it holds; Identity's recover_erasures_from_audit re-applies it. The
   drill checks the person is erased again, signed out, and the request is back in processing with every service
   asked again, and that a second run changes nothing.

Honest scope: both services run their real code against their own schemas with their own least-privilege logins, but
the signed HTTP hop between them is replaced by handing the exact request bodies and responses across in files (each
service runs in its own process, so they cannot call each other here). The signed transport has its own tests.
Run as an unprivileged OS user with PostgreSQL tools on PATH, as in CI.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class _Reply:
    def __init__(self, body, status=200):
        self.status, self.body = status, body if isinstance(body, bytes) else json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit):
        return self.body[:limit]


def _setup(service):
    sys.path.insert(0, str(ROOT / "services" / service))
    os.environ["DJANGO_SETTINGS_MODULE"] = "service.settings"
    import django
    django.setup()
    from django.db import connection
    if connection.vendor != "postgresql":
        raise RuntimeError("The drill must run on the disposable PostgreSQL fixture")


def _check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS", message, flush=True)


def identity(step, work):
    _setup("identity")
    import secrets
    import uuid
    from datetime import timedelta
    from io import StringIO
    from unittest.mock import patch
    from django.core.management import call_command
    from django.db import connection, transaction
    from django.utils import timezone
    from service import erasure, events, privacy_review
    from service.models import Account, ErasureJob, LoginSession, PrivacyRequest
    state = work / "state.json"

    if step == "seed":
        with transaction.atomic():
            person = Account.objects.create_user("drill-person@example.test", secrets.token_urlsafe(24), "Drill")
            admin = Account.objects.create_user("drill-admin@example.test", secrets.token_urlsafe(24), "Admin")
            LoginSession.objects.create(account=person, expires_at=timezone.now() + timedelta(days=1),
                                        refresh_digest=secrets.token_hex(32))
            item = PrivacyRequest.objects.create(account=person, kind="deletion", status="in_review",
                                                 reviewed_by=admin.id)
        state.write_text(json.dumps({"person": str(person.id), "admin": str(admin.id), "request": str(item.id)}))
        return

    ids = json.loads(state.read_text())
    if step == "erase":
        admin = Account.objects.get(pk=ids["admin"])
        with transaction.atomic():
            answer = privacy_review._approve_deletion(admin, {"id": ids["request"]}, timezone.now())
        _check(answer.status_code == 200, "the deletion is approved by Identity's own review step")
        creator = str(uuid.uuid4())
        for service in ("engagement", "creators", "business", "moderation", "content"):
            payload = {"request_id": ids["request"], "account_id": ids["person"], "service": service,
                       "counts": {"rows": 1}, "retained": []}
            if service == "creators":
                payload["creator_id"] = creator
            erasure.confirm(str(uuid.uuid4()), payload)
        _check(PrivacyRequest.objects.get(pk=ids["request"]).status == "completed",
               "every service confirmed and the erasure completed")
        sent = []

        def capture(service, path, method, payload, timeout):
            if (service, path, method) != ("audit", "/internal/security-events", "POST"):
                raise AssertionError("unexpected internal call")
            sent.append(json.loads(payload))
            return _Reply({"status": "ok"}, 201)
        with patch("service.management.commands.deliver_security_audit.signed_internal_request", capture):
            call_command("deliver_security_audit", "--limit", "1000", stdout=StringIO())
        (work / "to_audit.json").write_text(json.dumps(sent))
        return

    person = Account.objects.filter(pk=ids["person"]).first()
    live_sessions = LoginSession.objects.filter(account_id=ids["person"], revoked_at__isnull=True).count()
    item = PrivacyRequest.objects.get(pk=ids["request"])
    if step == "restored":
        _check(person is not None and person.is_active and person.email == "drill-person@example.test"
               and live_sessions == 1 and item.status == "in_review",
               "after pg_restore of the older backup the erased person is back: active, signed in, original email")
        return

    if step == "recover":
        pages = json.loads((work / "from_audit.json").read_text())
        asked = []

        def answer(service, path, method, payload, timeout):
            if (service, path, method) != ("audit", "/internal/audit/erasure-recovery", "POST"):
                raise AssertionError("unexpected internal call")
            asked.append(json.loads(payload))
            return _Reply(pages[len(asked) - 1])
        target = "service.management.commands.recover_erasures_from_audit.signed_internal_request"
        out = StringIO()
        with patch(target, answer):
            call_command("recover_erasures_from_audit", stdout=out)
        print(out.getvalue().strip(), flush=True)
        _check(ids["person"] not in out.getvalue(), "the command prints counts only, never an account id")
        person.refresh_from_db()
        _check(person.email == f"erased-{person.id.hex}@invalid" and person.display_name == "" and not person.is_active
               and not person.has_usable_password()
               and not LoginSession.objects.filter(account=person, revoked_at__isnull=True).exists(),
               "after recovery the person is erased again and signed out")
        item.refresh_from_db()
        _check(item.status == "processing" and ErasureJob.objects.filter(request=item).count() == 5,
               "the restored request is back in processing, never marked completed by recovery")
        with connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM event_outbox WHERE event_type = %s", [events.ERASURE_REQUESTED])
            rows = [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in cursor.fetchall()]
            services = sorted(row["service"] for row in rows if row["request_id"] == ids["request"])
        _check(services == ["business", "creators", "engagement"],
               "every service is asked to erase again (Moderation and Content follow Creators)")
        _check(Account.objects.get(pk=ids["admin"]).is_active, "the administrator's account is untouched")
        asked.clear()
        again = StringIO()
        with patch(target, answer):
            call_command("recover_erasures_from_audit", stdout=again)
        _check("Re-applied 0 recorded facts" in again.getvalue(), "a second run changes nothing")
        return
    raise ValueError("Unknown identity step")


def audit(step, work):
    _setup("audit")
    from django.test import RequestFactory
    from service.erasure_recovery import erasure_recovery
    from service.events import ingest
    from service.models import SecurityEvent

    def post(view, body):
        request = RequestFactory().post("/", body, content_type="application/json")
        request.service_caller = "identity"
        return view(request)

    if step == "ingest":
        for event in json.loads((work / "to_audit.json").read_text()):
            response = post(ingest, json.dumps(event, separators=(",", ":")))
            if response.status_code not in (200, 201):
                raise AssertionError("Audit refused an Identity event")
        person = json.loads((work / "state.json").read_text())["person"]
        kinds = set(SecurityEvent.objects.filter(producer="identity", actor_id=person).values_list("kind", flat=True))
        _check({"account.deactivated", "account.privacy_erasure_completed"} <= kinds,
               "Audit's own ingest stored the deactivation and the completed erasure in its own schema")
        return
    if step == "read":
        pages, cursor = [], None
        while True:
            response = post(erasure_recovery, json.dumps({"cursor": cursor} if cursor else {}))
            if response.status_code != 200:
                raise AssertionError("Audit's recovery source refused Identity")
            page = json.loads(response.content)
            pages.append(page)
            cursor = page["next_cursor"]
            if cursor is None:
                break
        (work / "from_audit.json").write_text(json.dumps(pages))
        _check(SecurityEvent.objects.filter(kind="audit.erasure_recovery_read").exists(),
               "Audit recorded that the recovery source was read")
        return
    raise ValueError("Unknown audit step")


def main():
    import tempfile
    from test_postgres_foundations import postgres_fixture
    tools = {tool: shutil.which(tool) for tool in ("pg_dump", "pg_restore")}
    if None in tools.values():
        raise RuntimeError("Missing PostgreSQL tools: pg_dump, pg_restore")
    with postgres_fixture() as (base, environments), tempfile.TemporaryDirectory(prefix="kolovibe-drill-") as scratch:
        work = Path(scratch)
        work.chmod(0o700)
        backup = work / "identity-older.dump"
        sample = environments["identity"]
        admin = dict(os.environ, PGHOST="127.0.0.1", PGPORT=sample["KOLOVIBE_DB_PORT"], PGUSER="kolovibe_ci_admin",
                     PGDATABASE="kolovibe_ci", PGSSLMODE="verify-full", PGSSLROOTCERT=sample["KOLOVIBE_DB_SSLROOTCERT"],
                     PGPASSWORD=(base / "admin-password").read_text())

        def step(service, name):
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--" + service, name, str(work)],
                           check=True, env=environments[service])
        step("identity", "seed")
        subprocess.run([tools["pg_dump"], "--format=custom", "--schema=identity", "--file", str(backup)],
                       check=True, env=admin)
        print("PASS the older identity backup is taken with pg_dump", flush=True)
        step("identity", "erase")
        step("audit", "ingest")
        subprocess.run([tools["pg_restore"], "--clean", "--if-exists", "--exit-on-error", "--single-transaction",
                        "--dbname", "kolovibe_ci", str(backup)], check=True, env=admin)
        print("PASS the older identity backup is restored with pg_restore", flush=True)
        step("identity", "restored")
        step("audit", "read")
        step("identity", "recover")
    print("Restore drill passed", flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] in ("--identity", "--audit"):
        (identity if sys.argv[1] == "--identity" else audit)(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
