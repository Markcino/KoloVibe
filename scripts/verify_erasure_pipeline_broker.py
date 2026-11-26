"""Decision C slice 2a on a REAL RabbitMQ over TLS: Identity -> Engagement erasure -> confirmation -> Identity.

Identity records an erasure request in its outbox; its own Celery app publishes it with the PROPOSED Identity broker
account; the production Engagement worker erases that account's likes, follows, shares and watch sessions and records
a confirmation; Engagement's dispatcher publishes it; the production Identity worker marks the job confirmed. The
proposed grants (generate_r1_secrets.PROPOSED_BROKER_PERMISSIONS) are proven least-privilege on the same broker.

It runs on disposable infrastructure only and changes nothing on staging. Needs PostgreSQL and RabbitMQ binaries, an
unprivileged user and a free loopback port 5671. Run from the repository root:
    python scripts/verify_erasure_pipeline_broker.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "ops"), str(HERE.parent / "services")]

import generate_r1_secrets as gen  # noqa: E402
from test_postgres_foundations import postgres_fixture  # noqa: E402
from verify_event_pipeline_broker import Broker, VHOST, eventually  # noqa: E402

STEPS = HERE / "erasure_pipeline_steps.py"
IDENTITY, ENGAGEMENT, POINTS = "kolovibe.identity", "kolovibe.engagement", "kolovibe.points"
ACCOUNTS = {**gen.BROKER_ACCOUNTS, **gen.PROPOSED_BROKER_ACCOUNTS}
PERMISSIONS = {**gen.BROKER_PERMISSIONS, **gen.PROPOSED_BROKER_PERMISSIONS}


class ErasureBroker(Broker):
    """The shared disposable broker, provisioned with the proposed Decision C grants and Identity's queue."""

    def __init__(self, base):
        super().__init__(base)
        self.passwords.update({name: "p" + uuid.uuid4().hex for name in gen.PROPOSED_BROKER_ACCOUNTS})

    def user(self, service):
        return "kv_admin" if service == "admin" else ACCOUNTS[service]

    def provision(self):
        self.ctl("add_vhost", VHOST)
        self.ctl("add_user", "kv_admin", self.passwords["admin"])
        self.ctl("set_permissions", "-p", VHOST, "kv_admin", ".*", ".*", ".*")
        for service, user in ACCOUNTS.items():
            self.ctl("add_user", user, self.passwords[service])
            self.ctl("set_permissions", "-p", VHOST, user, *PERMISSIONS[service])
        from kombu import Exchange, Queue

        with self.connection("admin") as connection:
            for name in (IDENTITY, ENGAGEMENT, POINTS):
                Queue(name, exchange=Exchange(name, type="direct", durable=True), routing_key=name,
                      durable=True)(connection.default_channel).declare()


class ErasurePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack, cls.workers = [], {}
        try:
            cls.postgres = postgres_fixture()
            _, cls.environments = cls.postgres.__enter__()
            cls.stack.append(lambda: cls.postgres.__exit__(None, None, None))
            cls.directory = tempfile.mkdtemp(prefix="kolovibe-erasure-")
            cls.stack.append(lambda: shutil.rmtree(cls.directory, ignore_errors=True))
            cls.broker = ErasureBroker(cls.directory)
            cls.stack.append(cls.broker.stop)
            cls.broker.start()
            cls.env = {service: dict(cls.environments[service], KOLOVIBE_ENV="local", SSL_CERT_FILE=str(cls.broker.ca),
                                     KOLOVIBE_RABBITMQ_URL=cls.broker.url(service))
                       for service in ("identity", "engagement")}
            for service, queue in (("engagement", ENGAGEMENT), ("identity", IDENTITY)):
                log = open(Path(cls.directory) / f"{service}-worker.log", "wb")
                worker = subprocess.Popen([sys.executable, str(STEPS), service, "worker", "{}"], env=cls.env[service],
                                          stdout=log, stderr=subprocess.STDOUT)
                cls.workers[service] = (worker, log)
                cls.stack.append(lambda w=worker, f=log: (w.terminate(), w.wait(timeout=30), f.close()))
                eventually(lambda q=queue, w=worker: cls.broker.consumers(q) >= 1 or w.poll() is not None, 60,
                           f"The {service} worker never registered a consumer")
                if worker.poll() is not None:
                    raise RuntimeError(f"{service} worker exited: "
                                       + Path(cls.directory, f"{service}-worker.log").read_text()[-800:])
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        while cls.stack:
            try:
                cls.stack.pop()()
            except Exception as error:
                print("teardown:", type(error).__name__, file=sys.stderr)

    def step(self, service, name, **arguments):
        result = subprocess.run([sys.executable, str(STEPS), service, name, json.dumps(arguments)], env=self.env[service],
                                capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        line = next(line for line in result.stdout.splitlines() if line.startswith("RESULT "))
        return json.loads(line[len("RESULT "):])

    def attempt(self, service, action):
        try:
            with self.broker.connection(service) as connection:
                action(connection)
            return "allowed"
        except Exception as error:
            return type(error).__name__

    def test_1_an_approved_deletion_is_erased_and_confirmed_across_the_real_broker(self):
        approved = self.step("identity", "approve")
        other = str(uuid.uuid4())
        self.step("engagement", "seed", account_id=approved["account_id"], other_id=other)
        self.assertEqual(self.step("identity", "dispatch_real"), {"sent": 1, "errors": []})

        def erased():
            state = self.step("engagement", "state", account_id=approved["account_id"], other_id=other)
            return state if state["person"]["VideoLike"] == 0 else None

        state = eventually(erased, 60, "Engagement never erased the account")
        self.assertEqual(state["person"], {"VideoLike": 0, "CreatorFollow": 0, "VideoShare": 0, "WatchSession": 0,
                                           "QualifiedWatch": 1})
        self.assertEqual(state["other"], {"VideoLike": 1, "CreatorFollow": 1, "VideoShare": 1, "WatchSession": 1,
                                          "QualifiedWatch": 0}, "another account is untouched")
        self.assertEqual(self.step("engagement", "dispatch_real"), {"sent": 1, "errors": []})
        result = eventually(lambda: (lambda s: s if s["confirmed"] else None)(
            self.step("identity", "state", request_id=approved["request_id"])), 60, "Identity never confirmed the job")
        self.assertEqual(result["counts"], {"likes": 1, "follows": 1, "shares": 1, "watch_sessions": 1})
        self.assertEqual(result["retained"], ["qualified_watches"])
        self.assertEqual(result["status"], "processing", "a retained category keeps the request open")
        self.assertEqual(result["audit"], 1)
        for queue in (ENGAGEMENT, IDENTITY):
            eventually(lambda q=queue: self.broker.queue_state(q) == (0, 0), 30, f"{queue} did not drain")

    def test_2_the_proposed_grants_are_least_privilege(self):
        from kombu import Exchange, Producer

        def publish(exchange):
            return lambda c: Producer(c.default_channel).publish(
                {"probe": True}, exchange=Exchange(exchange, type="direct", no_declare=True), routing_key=exchange,
                declare=[], retry=False, mandatory=False)

        self.assertEqual(self.attempt("identity", publish(ENGAGEMENT)), "allowed")
        self.assertEqual(self.attempt("engagement", publish(IDENTITY)), "allowed")
        refused = {
            "identity consumes the engagement queue": self.attempt("identity", lambda c: c.default_channel.basic_get(ENGAGEMENT)),
            "identity publishes to points": self.attempt("identity", publish(POINTS)),
            "identity declares a queue": self.attempt("identity", lambda c: c.default_channel.queue_declare("rogue.q")),
            "engagement consumes the identity queue": self.attempt("engagement", lambda c: c.default_channel.basic_get(IDENTITY)),
            "points publishes to identity": self.attempt("points", publish(IDENTITY)),
        }
        self.assertEqual(set(refused.values()), {"AccessRefused"}, refused)
        # Drain the two probes so the queues are clean for anything that follows.
        with self.broker.connection("admin") as connection:
            for queue in (ENGAGEMENT, IDENTITY):
                connection.default_channel.queue_purge(queue)


if __name__ == "__main__":
    unittest.main(verbosity=2)
