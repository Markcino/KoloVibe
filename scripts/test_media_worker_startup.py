"""Media-worker start-up regression tests: no remote control (`celery.pidbox`), approved queue, bounded worker.

The worker account on the broker may configure only the media queue and its exchange, so a worker that declares
`celery.pidbox` is refused with `ACCESS_REFUSED (403)` and exits. These tests run the real Celery 5 code against
Kombu's in-memory transport (never the staging broker). Each real-Celery check runs in a fresh interpreter because
Django settings, the Celery app and the in-memory broker state are process-global.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services"))

from staging_runtime import broker_ca, broker_url, capabilities, launch, roles  # noqa: E402
from validate_staging_stack import AWS_STACK, load_stack  # noqa: E402

PASSWORD = "p" * 40
URI = f"amqps://kolovibe_content_r1:{PASSWORD}@kolovibe-rabbitmq:5671/%2Fkolovibe"
QUEUE = "kolovibe.content.media"

# Runs in a child interpreter: real Celery and the real media_tasks module, with the staging secrets mocked.
CHILD = r'''
import json, sys, types
sys.path[:0] = ["services", "services/content"]
from django.conf import settings
spec = json.loads(sys.argv[2])
settings.configure(LOCAL_MEDIA_ENABLED=spec.get("media", True), ENVIRONMENT="staging", DATABASES={}, INSTALLED_APPS=[])
import staging_runtime
staging_runtime.broker_url = lambda: spec["broker"]
staging_runtime.broker_ca = lambda: spec["ca"]
out = {}
try:
    from service import media_tasks
except RuntimeError as error:
    print(json.dumps({"error": str(error)})); sys.exit(0)
app = media_tasks.app
mode = sys.argv[1]
if mode == "conf":
    c = app.conf
    out = {k: getattr(c, k) for k in (
        "worker_enable_remote_control", "worker_prefetch_multiplier", "task_default_queue", "task_acks_late",
        "task_reject_on_worker_lost", "task_time_limit", "broker_heartbeat", "broker_transport_options",
        "broker_connection_retry_on_startup", "accept_content", "task_serializer")}
    out["cert_reqs"] = int(c.broker_use_ssl["cert_reqs"])
    out["ca_certs"] = c.broker_use_ssl.get("ca_certs")
    out["broker_url_is_amqps"] = c.broker_url.startswith("amqps://")
elif mode == "start":
    # The real `worker_main` argument parser runs; only the final Worker.start is replaced.
    from celery.apps import worker
    from staging_runtime import roles
    def start(self):
        out.update(remote_control=self.app.conf.worker_enable_remote_control, options={
            k: v for k, v in self.options.items() if isinstance(v, (str, int, bool, type(None)))},
            queues=sorted(self.app.amqp.queues))
    worker.Worker.start = start
    if spec.get("force_remote_control_on"):
        app.conf.worker_enable_remote_control = True
    roles.run_celery("service.media_tasks:app", media_tasks.QUEUE)
elif mode == "declare":
    # A real worker on the in-memory transport: report every exchange and queue it declares and run one task.
    import time
    from celery.contrib.testing.worker import start_worker
    calls = []
    sys.modules["service.media_processing"] = types.SimpleNamespace(
        LeaseBusy=type("LeaseBusy", (Exception,), {}), process=lambda video_id: calls.append(video_id))
    app.conf.broker_url = "memory://"
    app.conf.broker_use_ssl = None
    app.conf.broker_transport_options = {}
    app.conf.task_always_eager = False
    with start_worker(app, perform_ping_check=False, pool="solo", queues=media_tasks.QUEUE, loglevel="ERROR"):
        app.send_task("kolovibe.content.process_video", args=["00000000-0000-0000-0000-000000000001"],
                      queue=media_tasks.QUEUE)
        for _ in range(100):
            if calls:
                break
            time.sleep(0.1)
        state = app.connection_for_read().default_channel.state
        out = {"exchanges": sorted(state.exchanges), "queues": sorted({b.queue for b in state.bindings}) if hasattr(state, "bindings") else None,
               "bindings": sorted(f"{b.exchange}->{b.queue}" for b in state.bindings), "processed": calls}
print(json.dumps(out, default=str))
'''


def child(mode, **spec):
    spec = {"broker": URI, "ca": str(ROOT / "README.md")} | spec
    result = subprocess.run([sys.executable, "-c", CHILD, mode, json.dumps(spec)], cwd=ROOT, capture_output=True,
                            text=True, timeout=120, env={**os.environ, "PYTHONWARNINGS": "ignore"})
    assert result.returncode == 0, result.stderr[-2000:]
    assert PASSWORD not in result.stdout + result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def settings(**kw):
    base = dict(ENVIRONMENT="staging", STAGING_CAPABILITIES=frozenset({"media"}), STAGING_PRIVILEGED=False)
    return types.SimpleNamespace(**(base | kw))


class RoleAndCapabilityTests(unittest.TestCase):
    def test_media_worker_role_resolves_to_the_media_app_queue_and_capability(self):
        self.assertEqual(roles.resolve("content", "media-worker"),
                         ("media", "celery", "service.media_tasks:app", QUEUE))

    def test_media_worker_role_is_refused_on_any_other_service_or_role(self):
        for pair in (("gateway", "media-worker"), ("engagement", "media-worker"), ("content", "worker"),
                     ("content", "consumer"), ("content", "")):
            with self.subTest(pair), self.assertRaises(RuntimeError):
                roles.resolve(*pair)

    def test_invalid_staging_capabilities_are_rejected(self):
        for value in ("media,bogus", "media,media", "watch,media", "Media", " media", "media,"):
            with self.subTest(value), self.assertRaises(RuntimeError):
                capabilities.parse(value)
        self.assertEqual(capabilities.parse("analytics,engagement,media,moderation"),
                         frozenset({"analytics", "engagement", "media", "moderation"}))
        with self.assertRaises(RuntimeError):
            capabilities.check("content", frozenset({"points"}), accounts=False, privileged=False)

    def run_role(self, config, *, setup=None):
        started = MagicMock()
        fake_django = MagicMock()
        fake_django.setup.side_effect = setup
        with patch.dict(sys.modules, {"django": fake_django, "django.conf": types.SimpleNamespace(settings=config)}), \
                patch.object(roles, "run_celery", started), patch.object(sys, "path", list(sys.path)), \
                patch.dict(os.environ, {}):
            launch.run_role(ROOT / "services", ROOT / "services/content", "content", "media-worker", 30, 100)
        return started

    def test_worker_starts_only_with_the_media_capability_in_staging(self):
        self.run_role(settings()).assert_called_once_with("service.media_tasks:app", QUEUE)
        for bad in (settings(STAGING_CAPABILITIES=frozenset()), settings(STAGING_CAPABILITIES=frozenset({"points"})),
                    settings(ENVIRONMENT="local"), settings(ENVIRONMENT="production")):
            started = MagicMock()
            with self.subTest(bad), self.assertRaisesRegex(RuntimeError, "not approved"):
                started = self.run_role(bad)
            started.assert_not_called()

    def test_worker_initialisation_failure_propagates_and_never_starts_celery(self):
        started = MagicMock()
        with patch.object(roles, "run_celery", started), self.assertRaises(RuntimeError):
            with patch.dict(sys.modules, {"django": MagicMock(setup=MagicMock(side_effect=RuntimeError("init"))),
                                          "django.conf": types.SimpleNamespace(settings=settings())}), \
                    patch.object(sys, "path", list(sys.path)), patch.dict(os.environ, {}):
                launch.run_role(ROOT / "services", ROOT / "services/content", "content", "media-worker", 30, 100)
        started.assert_not_called()


class RemoteControlTests(unittest.TestCase):
    def test_run_celery_disables_remote_control_before_the_worker_is_built(self):
        seen = {}
        app = MagicMock()
        app.conf.worker_enable_remote_control = True
        app.worker_main.side_effect = lambda argv: seen.update(rc=app.conf.worker_enable_remote_control, argv=argv)
        module = types.SimpleNamespace(app=app)
        with patch.dict(sys.modules, {"fake_media": module}):
            roles.run_celery("fake_media:app", QUEUE)
        self.assertIs(seen["rc"], False)
        self.assertEqual(seen["argv"][:3], ["worker", "-Q", QUEUE])

    def test_real_celery_parses_the_worker_arguments_with_the_approved_limits(self):
        out = child("start")
        self.assertIs(out["remote_control"], False)
        self.assertEqual(out["queues"], [QUEUE])
        options = out["options"]
        self.assertEqual((options["concurrency"], options["prefetch_multiplier"]), (1, 1))
        self.assertEqual((options["max_tasks_per_child"], options["max_memory_per_child"]), (20, 262144))
        self.assertIs(options["without_gossip"], True)
        self.assertIs(options["without_mingle"], True)
        # Celery event heartbeats are deliberately disabled; AMQP connection
        # heartbeats remain enabled by broker_heartbeat in the app config.
        self.assertIs(options["without_heartbeat"], True)

    def test_run_celery_corrects_an_app_that_enables_remote_control(self):
        self.assertIs(child("start", force_remote_control_on=True)["remote_control"], False)

    def test_worker_arguments_are_pinned(self):
        self.assertEqual(roles.celery_argv(QUEUE), [
            "worker", "-Q", QUEUE, "--concurrency=1", "--prefetch-multiplier=1", "--loglevel=WARNING",
            "--max-tasks-per-child=20", "--max-memory-per-child=262144", "--without-gossip", "--without-mingle",
            "--without-heartbeat"])

    def test_a_started_worker_declares_only_the_approved_queue_and_exchange(self):
        out = child("declare")
        self.assertNotIn("celery.pidbox", " ".join(out["exchanges"] + out["bindings"]))
        self.assertFalse([name for name in out["queues"] if "pidbox" in name])
        self.assertEqual(out["exchanges"], [QUEUE])
        self.assertEqual(out["bindings"], [f"{QUEUE}->{QUEUE}"])

    def test_a_task_published_to_the_media_queue_is_consumed_with_remote_control_off(self):
        self.assertEqual(child("declare")["processed"], ["00000000-0000-0000-0000-000000000001"])


class AppConfigurationTests(unittest.TestCase):
    def test_application_configuration(self):
        conf = child("conf")
        self.assertIs(conf["worker_enable_remote_control"], False)
        self.assertEqual(conf["task_default_queue"], QUEUE)
        self.assertEqual(conf["worker_prefetch_multiplier"], 1)
        # Reliability controls stay on: late acks, redelivery on worker loss, publisher confirms, bounded runtime.
        self.assertIs(conf["task_acks_late"], True)
        self.assertIs(conf["task_reject_on_worker_lost"], True)
        self.assertIs(conf["broker_transport_options"]["confirm_publish"], True)
        self.assertEqual(conf["task_time_limit"], 240)
        self.assertEqual(conf["broker_heartbeat"], 30)
        self.assertEqual((conf["accept_content"], conf["task_serializer"]), (["json"], "json"))

    def test_tls_is_required_and_verified_against_the_explicit_ca(self):
        conf = child("conf")
        self.assertTrue(conf["broker_url_is_amqps"])
        self.assertEqual(conf["cert_reqs"], 2)  # ssl.CERT_REQUIRED
        self.assertEqual(conf["ca_certs"], str(ROOT / "README.md"))

    def test_insecure_or_incomplete_broker_uris_are_rejected_without_leaking_the_secret(self):
        for uri in ("", f"amqp://u:{PASSWORD}@h:5672/v", f"redis://u:{PASSWORD}@h:6379/0", "amqps://h:5671/v",
                    "amqps://u@h:5671/v", f"amqps://u:{PASSWORD}@h:5672/v", f"amqps://u:{PASSWORD}@h:5671/v?heartbeat=0",
                    f"amqps://u:{PASSWORD}@h:5671/v#x", f"amqps://u:{PASSWORD}@h:bad/v"):
            with self.subTest(uri):
                out = child("conf", broker=uri)
                self.assertEqual(out, {"error": "Media worker requires an authenticated AMQPS broker"})

    def test_media_processing_must_be_enabled(self):
        self.assertEqual(child("conf", media=False), {"error": "Media processing is disabled"})


class SecretTests(unittest.TestCase):
    def secret_file(self, directory, text, mode=0o600):
        path = Path(directory) / "rabbitmq_url"
        path.write_text(text)
        path.chmod(mode)
        return str(path)

    def test_the_broker_uri_comes_only_from_an_owner_only_nonempty_valid_secret_file(self):
        with tempfile.TemporaryDirectory() as directory:
            good = self.secret_file(directory, URI + "\n")
            with patch.dict(os.environ, {"KOLOVIBE_RABBITMQ_URL_FILE": good}, clear=True):
                self.assertEqual(broker_url(), URI)
            for label, env, text, mode in (
                    ("missing variable", {}, None, 0),
                    ("missing file", {"KOLOVIBE_RABBITMQ_URL_FILE": directory + "/absent"}, None, 0),
                    ("group readable", {}, URI, 0o640),
                    ("empty", {}, "", 0o600),
                    ("plain amqp", {}, URI.replace("amqps", "amqp"), 0o600),
                    ("wrong port", {}, URI.replace("5671", "5672"), 0o600),
                    ("no password", {}, "amqps://kolovibe_content_r1@kolovibe-rabbitmq:5671/%2Fkolovibe", 0o600),
                    ("query", {}, URI + "?heartbeat=0", 0o600),
                    ("env variable", {"KOLOVIBE_RABBITMQ_URL": URI}, URI, 0o600)):
                with self.subTest(label):
                    env = dict(env)
                    if text is not None:
                        env["KOLOVIBE_RABBITMQ_URL_FILE"] = self.secret_file(directory, text, mode)
                    with patch.dict(os.environ, env, clear=True), self.assertRaises(RuntimeError) as caught:
                        broker_url()
                    self.assertNotIn(PASSWORD, str(caught.exception))

    def test_the_broker_ca_must_be_present_and_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "ca.pem"
            bad.write_text("not a certificate")
            for env in ({}, {"KOLOVIBE_RABBITMQ_CA_FILE": directory + "/absent"},
                        {"KOLOVIBE_RABBITMQ_CA_FILE": str(bad)}):
                with self.subTest(env), patch.dict(os.environ, env, clear=True), self.assertRaises(RuntimeError):
                    broker_ca()


class DeploymentConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inputs = {"STAGING_DB_NAME": "kolovibe_staging", "STAGING_DB_HOST": "172.31.16.20",
                  "KOLOVIBE_IMAGE": "ghcr.io/markcino/kolovibe/services@sha256:" + "a" * 64,
                  "KOLOVIBE_MEDIA_IMAGE": "ghcr.io/markcino/kolovibe/media-worker@sha256:" + "e" * 64,
                  "R2_ACCOUNT_ID": "1" * 32, "R2_MEDIA_BUCKET": "kolovibe-media", "SMTP_HOST": "smtp.example.test",
                  "SMTP_PORT": "587", "FROM_EMAIL": "noreply@example.test",
                  **{s.upper() + "_DB_USER": "runtime_" + s
                     for s in ("content", "engagement", "points", "moderation", "identity")}}
        cls.service = load_stack(AWS_STACK, inputs)["services"]["media-worker"]

    def test_the_service_is_non_root_read_only_unpublished_and_single_replica_capable(self):
        service = self.service
        self.assertEqual(service["user"], "10001:10001")
        self.assertIs(service["read_only"], True)
        self.assertEqual(service["tmpfs"], [str(Path(os.sep, "tmp"))])
        self.assertEqual(service["cap_drop"], ["ALL"])
        self.assertNotIn("ports", service)
        self.assertLessEqual(service["deploy"]["replicas"], 1)
        self.assertEqual(service["command"], ["--role", "media-worker"])
        self.assertEqual(service["environment"]["KOLOVIBE_STAGING_CAPABILITIES"], "analytics,engagement,media,moderation")
        self.assertEqual(service["deploy"]["resources"]["limits"]["cpus"], "1.0")

    def test_the_image_runs_as_the_unprivileged_user_in_its_final_stage(self):
        users = [line.split()[1] for line in (ROOT / "infra/docker/Dockerfile.service").read_text().splitlines()
                 if line.startswith("USER ")]
        self.assertEqual(users[-1], "10001:10001")


if __name__ == "__main__":
    unittest.main()
