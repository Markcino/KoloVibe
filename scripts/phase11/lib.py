"""Phase 11 test stack: every implemented service, the console, a real TLS RabbitMQ and the Points worker.

Disposable and local: a task-owned TLS PostgreSQL (one role per service), loopback HTTP, a private broker, captured
mail. It reuses the Phase 10 and journey harnesses instead of copying them. Run as an unprivileged user (PostgreSQL and
RabbitMQ refuse root) with the PostgreSQL and RabbitMQ binaries available. Nothing here contacts a network host.
"""

from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
ROOT = SCRIPTS.parent
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "ops"), str(ROOT / "services")]

import verify_local_journeys as vlj  # noqa: E402
from smtp_fixture import mailed_code  # noqa: E402
from test_postgres_foundations import postgres_fixture, secret_file  # noqa: E402

SERVICES = ("identity", "content", "creators", "moderation", "engagement", "points", "audit", "business", "gateway", "web")
STEPS = SCRIPTS / "event_pipeline_steps.py"


class Stack:
    def __init__(self, base, environments, ports, keys, broker=None):
        self.base, self.environments, self.ports, self.keys, self.broker = base, environments, ports, keys, broker
        self.processes = {}
        self.worker = None
        self.secrets = set()  # every credential this harness creates, so a test can prove none reached a log

    @classmethod
    def attach(cls, path):
        """Use a stack that stack_up.py is keeping alive (no broker handle; no process control)."""
        data = json.loads(Path(path).read_text())
        stack = cls(Path(data["base"]), data["environments"], data["ports"], {})
        stack.video_ids = data.get("video_ids", [])
        stack.creator_id = data.get("creator_id")
        return stack

    # ---- HTTP -------------------------------------------------------------------------------------
    def call(self, method, path, data=None, *, token=None, key=None, headers=None, port="gateway", raw=False, api=True):
        fields = dict(headers or {})
        if token:
            fields["Authorization"] = "Bearer " + token
        if key:
            fields["Idempotency-Key"] = key
        status, body = vlj.request(self.ports[port], ("/api/v1" if api else "") + path, method=method, data=data, headers=fields)
        if raw:
            return status, body
        try:
            return status, (json.loads(body) if body else None)
        except ValueError:
            return status, body

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, data=None, **kw):
        if path == "/auth/register" and isinstance(data, dict) and "accepted" not in data:
            data = {**data, "accepted": self.accepted_versions()}  # Decision B: fixture accounts accept the current texts
        return self.call("POST", path, {} if data is None else data, **kw)

    def accepted_versions(self):
        versions = {}
        for kind in ("terms", "privacy"):
            status, document = self.call("GET", f"/legal/{kind}", None)
            assert status == 200, ("legal", kind, status)
            versions[kind] = document["version"]
        return versions

    # ---- accounts -----------------------------------------------------------------------------------
    def new_user(self, label=None, *, verify=True):
        label = label or secrets.token_hex(4)
        body = {"email": f"u{label}@example.test", "display_name": f"User {label}", "password": secrets.token_urlsafe(24)}
        status, _ = self.post("/auth/register", body)
        assert status == 201, ("register", status)
        user = {**body}
        self.secrets.add(body["password"])
        if verify:
            code = mailed_code(self.base)
            status, _ = self.post("/auth/verify", {"email": body["email"], "code": code})
            assert status == 200, ("verify", status)
        return user

    def login(self, user):
        status, answer = self.post("/auth/login", {"email": user["email"], "password": user["password"]})
        assert status == 200, ("login", status, answer)
        self.secrets.update((answer["access_token"], answer["refresh_token"]))
        return answer

    def signed_in(self, label=None):
        user = self.new_user(label)
        tokens = self.login(user)
        return user, tokens

    def arm_fixture_videos(self, account_id, duration_ms=3000):
        """Make the seeded videos watchable and credit their creator to `account_id` (what an operator's data would hold)."""
        import datetime

        with self.db("creators") as c:
            c.execute("update creators.service_creatorprofile set user_id=%s where handle='fixture-creator'", (account_id,))
        with self.db("identity") as c:
            c.execute("UPDATE identity.service_account SET role='creator' WHERE id=%s", (account_id,))
        self.approve_creator(account_id, profile_handle="fixture-creator")
        with self.db("content") as c:
            expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
            for video in self.video_ids:
                c.execute("update content.service_video set duration_ms=%s, duration_seconds=%s, provider_asset_id=%s, "
                          "published_at=now() where id=%s", (duration_ms, duration_ms // 1000, f"playback/{video}/{uuid.uuid4()}.mp4", video))
                c.execute("insert into content.service_mediaupload (id,video_id,expected_bytes,expires_at,source_etag) "
                          "values (%s,%s,%s,%s,'') on conflict do nothing", (uuid.uuid4(), video, 1000, expires))

    def approve_creator(self, account_id, profile_handle=None):
        """Give `account_id` an approved CreatorApplication linked to a profile: what the invitation and review flow leaves behind."""
        with self.db("creators") as c:
            if profile_handle:
                profile = c.execute("select id from creators.service_creatorprofile where handle=%s", (profile_handle,)).fetchone()[0]
            else:
                profile = uuid.uuid4()
                c.execute("insert into creators.service_creatorprofile (id,user_id,handle,bio,status,reviewed_at,created_at,display_name,location) "
                          "values (%s,%s,%s,'','active',now(),now(),'Fixture Creator','')", (profile, account_id, "c-" + uuid.uuid4().hex[:8]))
            c.execute("delete from creators.service_creatorapplication where profile_id=%s and account_id<>%s", (profile, account_id))
            c.execute("insert into creators.service_creatorapplication (account_id,invited_by,invited_at,status,profile_id,attestation_version,submitted_at,reviewed_by,reviewed_at) "
                      "values (%s,%s,now(),'approved',%s,'DEC-004-pilot-v1',now(),%s,now()) on conflict (account_id) do update set status='approved', profile_id=excluded.profile_id",
                      (account_id, uuid.uuid4(), profile, uuid.uuid4()))
        with self.db("identity") as c:
            c.execute("UPDATE identity.service_account SET role='creator' WHERE id=%s", (account_id,))
        return profile

    def db(self, service):
        import psycopg

        env = self.environments[service]
        return psycopg.connect(dbname=env["KOLOVIBE_DB_NAME"], user=env["KOLOVIBE_DB_USER"], host="127.0.0.1",
                               port=env["KOLOVIBE_DB_PORT"], password=Path(env["KOLOVIBE_DB_PASSWORD_FILE"]).read_text(),
                               sslmode="verify-full", sslrootcert=env["KOLOVIBE_DB_SSLROOTCERT"], autocommit=True)

    def privileged(self, role, label=None):
        """An account with `role` and enrolled MFA, using the existing enrollment command. Returns (user, recovery code)."""
        import pyotp

        label = (label or secrets.token_hex(3)) + "-" + role
        user = self.new_user(label)
        with self.db("identity") as connection:
            actor = connection.execute("UPDATE identity.service_account SET role=%s WHERE email=%s RETURNING id",
                                       (role, user["email"])).fetchone()[0]
        factor = pyotp.random_base32()
        secret_file(self.base / (label + "-factor"), factor)
        secret_file(self.base / (label + "-code"), pyotp.TOTP(factor).now())
        env = dict(self.environments["identity"], KOLOVIBE_ENROLLMENT_SECRET_FILE=str(self.base / (label + "-factor")),
                   KOLOVIBE_ENROLLMENT_CODE_FILE=str(self.base / (label + "-code")))
        code = ("import os,sys,django;os.environ['DJANGO_SETTINGS_MODULE']='service.settings';django.setup();"
                "from django.conf import settings;settings.STAGING_PRIVILEGED=True;"
                "from django.core.management import call_command;"
                "call_command('enroll_privileged_mfa', account_id=sys.argv[1], recovery_file=sys.argv[2], "
                "approval_reference='disposable-phase11-fixture')")
        result = subprocess.run([sys.executable, "-c", code, str(actor), str(self.base / (label + "-recovery"))],
                                cwd=ROOT / "services/identity", env=env, capture_output=True, timeout=30)
        assert result.returncode == 0, "privileged enrollment failed"
        lines = (self.base / (label + "-recovery")).read_text().splitlines()
        self.secrets.update(lines)
        self.secrets.add(factor)
        user.update(actor=str(actor), factor=factor, recovery=lines[0], recoveries=lines)
        return user

    # ---- event path -----------------------------------------------------------------------------------
    def step(self, service, name, **arguments):
        env = dict(self.environments[service], KOLOVIBE_ENV="local")
        if self.broker:
            env.update(SSL_CERT_FILE=str(self.broker.ca), KOLOVIBE_RABBITMQ_URL=self.broker.url(service))
        result = subprocess.run([sys.executable, str(STEPS), service, name, json.dumps(arguments)], env=env,
                                capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stderr[-800:]
        line = next(line for line in result.stdout.splitlines() if line.startswith("RESULT "))
        return json.loads(line[len("RESULT "):])

    def dispatch(self):
        """Run the real Engagement outbox dispatcher once against the real broker. Returns (exit code, output)."""
        env = dict(self.environments["engagement"], KOLOVIBE_ENV="local", KOLOVIBE_LOCAL_POINTS_ENABLED="1",
                   SSL_CERT_FILE=str(self.broker.ca), KOLOVIBE_RABBITMQ_URL=self.broker.url("engagement"))
        result = subprocess.run([sys.executable, "manage.py", "dispatch_engagement_events", "--limit", "500"],
                                cwd=ROOT / "services/engagement", env=env, capture_output=True, text=True, timeout=180)
        return result.returncode, (result.stdout + result.stderr)[-600:]

    def start_worker(self):
        env = dict(self.environments["points"], KOLOVIBE_ENV="local", SSL_CERT_FILE=str(self.broker.ca),
                   KOLOVIBE_RABBITMQ_URL=self.broker.url("points"))
        self.worker_log = open(self.base / "points-worker.log", "ab")
        self.worker = subprocess.Popen([sys.executable, str(STEPS), "points", "worker", "{}"], env=env,
                                       stdout=self.worker_log, stderr=subprocess.STDOUT)
        return self.worker

    def stop_worker(self, kill=False):
        if self.worker and self.worker.poll() is None:
            self.worker.kill() if kill else self.worker.terminate()
            self.worker.wait(timeout=30)


def eventually(check, seconds=30, message="condition not reached"):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.3)
    raise AssertionError(message)


@contextmanager
def stack(broker=True):
    import generate_r1_secrets  # noqa: F401  (the broker provisions from its permission table)
    from verify_event_pipeline_broker import Broker

    with postgres_fixture() as (base, environments), ExitStack() as exit_stack:
        ports, reservations = {}, {}
        for service in SERVICES:
            sock = exit_stack.enter_context(socket.socket())
            sock.bind(("127.0.0.1", 0))
            ports[service], reservations[service] = sock.getsockname()[1], sock
        keys = {service: secrets.token_urlsafe(48) for service in SERVICES if service not in {"gateway", "web"}}
        moderation_key = secrets.token_urlsafe(48)
        from cryptography.fernet import Fernet

        secret_file(base / "mfa-key", Fernet.generate_key().decode())
        environments["identity"]["KOLOVIBE_MFA_ENCRYPTION_KEY_FILE"] = str(base / "mfa-key")
        creator_id, video_ids = uuid.uuid4(), [uuid.uuid4() for _ in range(21)]
        vlj.seed(environments["creators"], creator_id, video_ids)
        vlj.seed(environments["content"], creator_id, video_ids)
        environments["web"] = {**environments["gateway"], "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
                               "KOLOVIBE_GATEWAY_URL": f"http://127.0.0.1:{ports['gateway']}"}
        the_broker = None
        if broker:
            directory = Path(base) / "rmq"
            directory.mkdir()
            the_broker = Broker(directory)
            exit_stack.callback(the_broker.stop)
            the_broker.start()
        for service in SERVICES:
            environment = dict(environments[service])
            if service == "gateway":
                # Phase 12: per-origin limits only count when the edge vouches for a client address. A real edge overwrites this
                # header on every request; here a test that wants an origin sends it. NOTE: no deployment manifest sets it (D12-001).
                environment["KOLOVIBE_TRUSTED_CLIENT_IP_HEADER"] = "X-Phase11-Client-IP"
                environment["KOLOVIBE_LOCAL_MEDIA_ENABLED"] = "1"
                environment["KOLOVIBE_LOCAL_BUSINESS_ENABLED"] = "1"
                for peer, key in keys.items():
                    environment[f"KOLOVIBE_{peer.upper()}_URL"] = f"http://127.0.0.1:{ports[peer]}"
                    environment[f"KOLOVIBE_GATEWAY_OUTBOUND_KEY_{peer.upper()}"] = key
            elif service != "web":
                environment["KOLOVIBE_CALLER_GATEWAY_KEY"] = keys[service]
            if service in {"gateway", "content", "moderation"}:
                environment["KOLOVIBE_LOCAL_MODERATION_ENABLED"] = "1"
            if service in {"gateway", "content", "engagement"}:
                environment["KOLOVIBE_LOCAL_MEDIA_ENABLED"] = "1"  # Content serves the internal watch and media routes
            if service in {"gateway", "engagement", "points"}:
                environment["KOLOVIBE_LOCAL_POINTS_ENABLED"] = "1"
            if service == "content":
                environment["KOLOVIBE_CALLER_MODERATION_KEY"] = moderation_key
            if service == "moderation":
                environment["KOLOVIBE_MODERATION_OUTBOUND_KEY_CONTENT"] = moderation_key
                environment["KOLOVIBE_CONTENT_URL"] = f"http://127.0.0.1:{ports['content']}"
            if service == "content":
                # Well-formed, throwaway values: the SigV4 playback signer works offline and no network host is contacted.
                secret_file(base / "r2-access", "A" * 24)
                secret_file(base / "r2-secret", "B" * 40)
                environment.update(KOLOVIBE_R2_ACCOUNT_ID="0123456789abcdef0123456789abcdef", KOLOVIBE_R2_MEDIA_BUCKET="kolovibe-fixture",
                                   KOLOVIBE_R2_ACCESS_KEY_FILE=str(base / "r2-access"), KOLOVIBE_R2_SECRET_KEY_FILE=str(base / "r2-secret"))
            if the_broker and service in {"engagement", "points"}:
                environment.update(SSL_CERT_FILE=str(the_broker.ca), KOLOVIBE_RABBITMQ_URL=the_broker.url(service))
            log = exit_stack.enter_context((Path(base) / f"{service}.log").open("w"))
            reservations[service].close()
            process = subprocess.Popen([sys.executable, str(SCRIPTS / "verify_local_journeys.py"), "--serve", service,
                                        str(ports[service])], env=environment, stdout=log, stderr=log)
            exit_stack.callback(vlj.stop, process)
            deadline = time.monotonic() + 40
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"{service} exited before readiness")
                try:
                    if vlj.request(ports[service], "/health/live")[0] == 200:
                        break
                except (OSError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"{service} readiness timed out")
                time.sleep(0.2)
        instance = Stack(Path(base), environments, ports, keys, the_broker)
        instance.creator_id, instance.video_ids = creator_id, video_ids
        if the_broker:
            instance.start_worker()
            exit_stack.callback(instance.stop_worker, True)
            eventually(lambda: the_broker.consumers("kolovibe.points") >= 1, 60, "Points worker did not connect")
        yield instance


VHOST = "/kolovibe"
CURRENT = None  # the running Stack; set by runner.py before the tests are loaded
