"""Engagement outbox -> REAL RabbitMQ over TLS -> real Points worker -> append-only ledger.

scripts/verify_event_pipeline.py replaces the broker with a recording publisher, so it cannot show what RabbitMQ itself
does. This script closes that gap on disposable infrastructure: a private RabbitMQ with a TLS listener on 5671 (the only
port the services accept) and a throwaway CA; the three per-service accounts provisioned from the SAME least-privilege
table the secrets generator emits (generate_r1_secrets.BROKER_PERMISSIONS); the real Engagement dispatcher publishing
through its own Celery app; the production Points worker (staging_runtime.roles.run_celery) consuming; and the real
Points database applying the award. It also proves what the accounts are NOT allowed to do.

It does not prove the deployed broker's configuration, Swarm networking, the staging CA or broker memory sizing; those
remain owner staging checks.

Needs: PostgreSQL and RabbitMQ binaries, an unprivileged user (both refuse root), a free port 5671 on loopback.
Run from the repository root:  python scripts/verify_event_pipeline_broker.py
Set KOLOVIBE_RABBITMQ_SBIN to the directory holding rabbitmq-server and rabbitmqctl if they are not under /usr/lib/rabbitmq.
"""

import glob
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(HERE / "ops"), str(ROOT / "services")]

from test_postgres_foundations import postgres_fixture  # noqa: E402
import generate_r1_secrets as gen  # noqa: E402

STEPS = HERE / "event_pipeline_steps.py"
TLS_PORT = gen.BROKER_PORT  # 5671: the services reject any other port
VHOST = gen.BROKER_VHOST
POINTS, ENGAGEMENT, CONTENT = "kolovibe.points", "kolovibe.engagement", "kolovibe.content.media"


def find_sbin():
    configured = os.environ.get("KOLOVIBE_RABBITMQ_SBIN")
    candidates = [configured] if configured else sorted(glob.glob("/usr/lib/rabbitmq/lib/rabbitmq_server-*/sbin"))
    for directory in candidates:
        if directory and (Path(directory) / "rabbitmq-server").exists() and (Path(directory) / "rabbitmqctl").exists():
            return Path(directory)
    raise RuntimeError("RabbitMQ is not installed (rabbitmq-server and rabbitmqctl); set KOLOVIBE_RABBITMQ_SBIN")


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Broker:
    """A private, disposable RabbitMQ node with one TLS listener."""

    def __init__(self, base):
        if os.geteuid() == 0:
            raise RuntimeError("Run as an unprivileged user: RabbitMQ and PostgreSQL both refuse to run as root")
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", TLS_PORT)) == 0:
                raise RuntimeError(f"Port {TLS_PORT} is already in use; stop the other broker first")
        self.sbin, self.base = find_sbin(), Path(base)
        self.ca, self.name = self.base / "ca.pem", f"kvtest{secrets.token_hex(3)}@localhost"
        self.passwords = {name: secrets.token_urlsafe(24) for name in ("admin", *gen.BROKER_ACCOUNTS)}
        self.process = None
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.base),
            "RABBITMQ_NODENAME": self.name, "RABBITMQ_NODE_IP_ADDRESS": "127.0.0.1",
            "RABBITMQ_DIST_PORT": str(free_port()), "RABBITMQ_MNESIA_BASE": str(self.base / "mnesia"),
            "RABBITMQ_LOG_BASE": str(self.base / "log"), "RABBITMQ_CONFIG_FILE": str(self.base / "rabbitmq"),
            "RABBITMQ_ENABLED_PLUGINS_FILE": str(self.base / "plugins"),
        }

    def start(self):
        openssl = shutil.which("openssl")
        if openssl is None:
            raise RuntimeError("openssl is required")
        quiet = {"check": True, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        key, request, cert, authority_key = (self.base / name for name in ("srv.key", "srv.csr", "srv.pem", "ca.key"))
        subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=kv-test-ca",
                        "-keyout", str(authority_key), "-out", str(self.ca)], **quiet)
        subprocess.run([openssl, "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=localhost",
                        "-keyout", str(key), "-out", str(request)], **quiet)
        extension = self.base / "ext.cnf"
        extension.write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=CA:FALSE\n")
        subprocess.run([openssl, "x509", "-req", "-in", str(request), "-CA", str(self.ca), "-CAkey", str(authority_key),
                        "-CAcreateserial", "-days", "1", "-extfile", str(extension), "-out", str(cert)], **quiet)
        for path in (key, authority_key):
            path.chmod(0o600)
        (self.base / "plugins").write_text("[].\n")
        (self.base / "rabbitmq.conf").write_text(
            f"listeners.tcp = none\nlisteners.ssl.default = {TLS_PORT}\n"
            f"ssl_options.cacertfile = {self.ca}\nssl_options.certfile = {cert}\nssl_options.keyfile = {key}\n"
            "ssl_options.verify = verify_none\nssl_options.fail_if_no_peer_cert = false\n"
            "loopback_users.guest = false\nlog.console = false\n")
        self.process = subprocess.Popen([str(self.sbin / "rabbitmq-server")], env=self.env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 90
        while not (self.base / ".erlang.cookie").exists():
            if time.monotonic() > deadline or self.process.poll() is not None:
                raise RuntimeError("RabbitMQ did not start")
            time.sleep(0.5)
        self.ctl("await_startup", timeout=120)
        self.provision()

    def ctl(self, *args, timeout=60, check=True):
        cookie = (self.base / ".erlang.cookie").read_text().strip()
        result = subprocess.run([str(self.sbin / "rabbitmqctl"), "--erlang-cookie", cookie, "-q", *args], env=self.env,
                                capture_output=True, text=True, timeout=timeout)
        if check and result.returncode != 0:
            raise RuntimeError("rabbitmqctl " + args[0] + " failed: " + result.stderr[-300:])
        return result.stdout

    def provision(self):
        """What the operator does once: vhost, accounts with least-privilege grants, and the queue topology."""
        self.ctl("add_vhost", VHOST)
        self.ctl("add_user", "kv_admin", self.passwords["admin"])
        self.ctl("set_permissions", "-p", VHOST, "kv_admin", ".*", ".*", ".*")
        for service, user in gen.BROKER_ACCOUNTS.items():
            self.ctl("add_user", user, self.passwords[service])
            self.ctl("set_permissions", "-p", VHOST, user, *gen.BROKER_PERMISSIONS[service])
        from kombu import Exchange, Queue

        with self.connection("admin") as connection:
            channel = connection.default_channel
            for name in (POINTS, ENGAGEMENT, CONTENT):
                Queue(name, exchange=Exchange(name, type="direct", durable=True), routing_key=name,
                      durable=True)(channel).declare()

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.ctl("stop", check=False, timeout=60)
                self.process.wait(timeout=60)
            except (subprocess.TimeoutExpired, RuntimeError):
                self.process.kill()

    def user(self, service):
        return "kv_admin" if service == "admin" else gen.BROKER_ACCOUNTS[service]

    def url(self, service):
        return (f"amqps://{self.user(service)}:{self.passwords[service]}@localhost:{TLS_PORT}/"
                + quote(VHOST, safe=""))

    def connection(self, service):
        from kombu import Connection

        return Connection(self.url(service), ssl={"ca_certs": str(self.ca), "cert_reqs": ssl.CERT_REQUIRED},
                          transport_options={"confirm_publish": True}, connect_timeout=10)

    def queue_state(self, name):
        for line in self.ctl("list_queues", "-p", VHOST, "name", "messages_ready", "messages_unacknowledged").splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[0] == name:
                return int(parts[1]), int(parts[2])
        raise RuntimeError("Queue not found: " + name)

    def consumers(self, queue):
        return sum(1 for line in self.ctl("list_consumers", "-p", VHOST).splitlines() if line.startswith(queue))


def eventually(check, seconds=45, message="condition not reached"):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.4)
    raise AssertionError(message)


class BrokerPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = []
        try:
            cls.postgres = postgres_fixture()
            cls.base, cls.environments = cls.postgres.__enter__()
            cls.stack.append(lambda: cls.postgres.__exit__(None, None, None))
            cls.directory = tempfile.mkdtemp(prefix="kolovibe-rmq-")
            cls.stack.append(lambda: shutil.rmtree(cls.directory, ignore_errors=True))
            cls.broker = Broker(cls.directory)
            cls.stack.append(cls.broker.stop)
            cls.broker.start()
            cls.env = {service: dict(cls.environments[service], KOLOVIBE_ENV="local", SSL_CERT_FILE=str(cls.broker.ca),
                                     KOLOVIBE_RABBITMQ_URL=cls.broker.url(service)) for service in ("engagement", "points")}
            cls.log = open(Path(cls.directory) / "points-worker.log", "wb")
            cls.worker = subprocess.Popen([sys.executable, str(STEPS), "points", "worker", "{}"], env=cls.env["points"],
                                          stdout=cls.log, stderr=subprocess.STDOUT)
            cls.stack.append(cls.stop_worker)
            eventually(lambda: cls.broker.consumers(POINTS) >= 1 or cls.worker.poll() is not None, 60,
                       "The Points worker never registered a consumer")
            if cls.worker.poll() is not None:
                raise RuntimeError("Points worker exited: " + Path(cls.directory, "points-worker.log").read_text()[-800:])
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def stop_worker(cls):
        if cls.worker.poll() is None:
            cls.worker.terminate()
            try:
                cls.worker.wait(timeout=30)
            except subprocess.TimeoutExpired:
                cls.worker.kill()
        cls.log.close()

    @classmethod
    def tearDownClass(cls):
        while cls.stack:
            try:
                cls.stack.pop()()
            except Exception as error:  # keep tearing down; report the type only
                print("teardown:", type(error).__name__, file=sys.stderr)

    def step(self, service, name, **arguments):
        result = subprocess.run([sys.executable, str(STEPS), service, name, json.dumps(arguments)], env=self.env[service],
                                capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        line = next(line for line in result.stdout.splitlines() if line.startswith("RESULT "))
        return json.loads(line[len("RESULT "):])

    def state(self, creators):
        return self.step("points", "state", creators=creators)

    def settled(self):
        """The broker holds nothing for Points: everything published has been consumed and acknowledged."""
        return eventually(lambda: self.broker.queue_state(POINTS) == (0, 0), 30, "Points queue did not drain")

    def attempt(self, service, action):
        try:
            with self.broker.connection(service) as connection:
                action(connection)
            return "allowed"
        except Exception as error:
            return type(error).__name__

    # --- the boundary contract on the real broker ------------------------------------------------

    def test_1_a_qualified_view_crosses_the_real_broker_to_exactly_one_ledger_entry(self):
        created = self.step("engagement", "qualify", count=1)
        sent = self.step("engagement", "dispatch_real")
        self.assertEqual((sent["errors"], sent["outbox_published"]), ([], sent["outbox_total"]))
        creators = created["creators"]
        state = eventually(lambda: (lambda s: s if s["entries"] == 1 else None)(self.state(creators)), 45,
                           "The real worker never posted the award")
        self.assertEqual((state["entries"], state["balance"]), (1, 1))
        self.assertEqual(state["receipts"], {"pending": 0, "posted": 1, "withheld": 0})
        self.settled()

    def test_2_the_same_event_delivered_twice_by_the_real_broker_has_one_effect(self):
        created = self.step("engagement", "qualify", count=1)
        self.step("engagement", "dispatch_real")
        creators = created["creators"]
        eventually(lambda: self.state(creators)["entries"] == 1, 45, "first delivery not applied")
        self.settled()
        self.step("engagement", "reset_outbox")  # same event ids are published a second time
        again = self.step("engagement", "dispatch_real")
        self.assertEqual(again["errors"], [])
        self.settled()
        state = self.state(creators)
        self.assertEqual((state["entries"], state["receipts"]["posted"]), (1, 1))

    def test_3_a_broker_outage_loses_nothing_and_the_retry_delivers_once(self):
        created = self.step("engagement", "qualify", count=1)
        creators = created["creators"]
        self.broker.ctl("stop_app")
        try:
            down = self.step("engagement", "dispatch_real")
            self.assertTrue(down["errors"], "A dead broker must surface as an error")
            self.assertLess(down["outbox_published"], down["outbox_total"])  # still in the outbox, never marked published
            self.assertEqual(self.state(creators)["entries"], 0)
        finally:
            self.broker.ctl("start_app", timeout=120)
        eventually(lambda: self.broker.consumers(POINTS) >= 1, 60, "worker did not reconnect after the broker returned")
        up = self.step("engagement", "dispatch_real")
        self.assertEqual(up["errors"], [])
        eventually(lambda: self.state(creators)["entries"] == 1, 45, "the retry did not post")
        self.settled()
        self.assertEqual(self.state(creators)["entries"], 1)

    def test_4_engagement_can_write_to_the_points_exchange_and_nothing_else(self):
        from kombu import Exchange

        def publish(exchange, key):
            return lambda connection: connection.Producer().publish(
                {"probe": 1}, exchange=Exchange(exchange, no_declare=True) if exchange else "", routing_key=key,
                declare=[], retry=False)

        def consume(queue):
            return lambda connection: connection.default_channel.basic_get(queue)

        self.assertEqual(self.attempt("engagement", publish(POINTS, POINTS)), "allowed")
        self.settled_or_drain()
        refused = {
            "consume the Points queue": self.attempt("engagement", consume(POINTS)),
            "declare a new queue": self.attempt("engagement", lambda c: c.default_channel.queue_declare("rogue.queue")),
            "publish to the content exchange": self.attempt("engagement", publish(CONTENT, CONTENT)),
            "publish via the default exchange": self.attempt("engagement", publish("", POINTS)),
        }
        for what, outcome in refused.items():
            self.assertEqual(outcome, "AccessRefused", f"Engagement was able to {what}: {outcome}")

    def settled_or_drain(self):
        # The probe above is not a task; the worker rejects it. Wait until the queue is quiet before the next test.
        eventually(lambda: self.broker.queue_state(POINTS)[0] == 0, 30, "probe message not consumed")

    def test_5_points_and_content_accounts_cannot_reach_each_others_queues(self):
        from kombu import Exchange

        def publish(exchange):
            return lambda c: c.Producer().publish({"probe": 1}, exchange=Exchange(exchange, no_declare=True),
                                                  routing_key=exchange, declare=[], retry=False)

        for service, other in (("points", ENGAGEMENT), ("points", CONTENT), ("content", POINTS), ("content", ENGAGEMENT)):
            self.assertEqual(self.attempt(service, publish(other)), "AccessRefused", f"{service} reached {other}")
            self.assertEqual(self.attempt(service, lambda c, q=other: c.default_channel.basic_get(q)), "AccessRefused",
                             f"{service} read {other}")
        # Each account does work on its own resources: Points on its exchange (what a retry uses), Content on its queue.
        self.assertEqual(self.attempt("points", publish(POINTS)), "allowed")
        self.settled_or_drain()
        self.assertEqual(self.attempt("content", publish(CONTENT)), "allowed")
        self.assertEqual(self.attempt("content", lambda c: c.default_channel.basic_get(CONTENT)), "allowed")

    def test_6_engagements_own_queue_works_under_its_grants(self):
        before = self.broker.queue_state(ENGAGEMENT)[0]
        self.step("engagement", "record_other")
        sent = self.step("engagement", "dispatch_real")
        self.assertEqual(sent["errors"], [], sent["detail"])
        self.assertEqual(self.broker.queue_state(ENGAGEMENT)[0], before + 1)
        got = self.attempt("engagement", lambda c: c.default_channel.basic_get(ENGAGEMENT))
        self.assertEqual(got, "allowed")  # it may consume its own queue, as its consumer role does

    def test_7_a_malformed_task_envelope_is_rejected_and_the_consumer_keeps_working(self):
        """Phase 11 D11-001: a `task` header with a list body used to kill the worker, which then died again on every restart."""
        from kombu import Exchange

        created = self.step("engagement", "qualify", count=1)
        with self.broker.connection("points") as connection:
            for body in ([1, 2, 3], {"id": "x"}):
                connection.Producer().publish(body, exchange=Exchange(POINTS, no_declare=True), routing_key=POINTS, declare=[], retry=False,
                                              headers={"task": "kolovibe.points.event"})
        eventually(lambda: self.broker.queue_state(POINTS) == (0, 0), 30, "malformed messages are stuck or looping in the queue")
        self.assertIsNone(self.worker.poll(), "the worker died on a malformed task envelope")
        self.step("engagement", "dispatch_real")
        creators = created["creators"]
        eventually(lambda: self.state(creators)["entries"] == 1, 45, "a valid event after the malformed ones was not applied")
        self.settled()


if __name__ == "__main__":
    unittest.main(verbosity=2)
