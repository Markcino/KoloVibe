"""Regression tests for Celery/RabbitMQ worker configuration without a broker."""
import importlib.util
import os
from pathlib import Path
import ssl
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class FakeCelery:
    def __init__(self, name):
        self.name = name
        self.conf = types.SimpleNamespace(update=self.update)
        self.settings = {}

    def update(self, **kwargs):
        self.settings.update(kwargs)


def load_worker(service):
    path = ROOT / "services" / service / "service" / "celery_app.py"
    spec = importlib.util.spec_from_file_location("worker_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrokerSecurityTests(unittest.TestCase):
    def test_rejects_unsafe_broker_configuration(self):
        unsafe = (
            "",
            "amqp://user:pass@rabbitmq:5672/vhost",
            "redis://user:pass@localhost:6379/0",
            "amqps://rabbitmq:5671/vhost",
            "amqps://user@rabbitmq:5671/vhost",
            "amqps://user:pass@rabbitmq:5672/vhost",
            "amqps://user:pass@rabbitmq:5671/vhost?heartbeat=0",
            "amqps://user:pass@rabbitmq:5671/vhost#token",
            "amqps://user:pass@rabbitmq:bad/vhost",
        )
        for service in ("engagement", "points"):
            for value in unsafe:
                with self.subTest(service=service, value=value):
                    with patch.dict(os.environ, {
                        "KOLOVIBE_ENV": "local",
                        "KOLOVIBE_RABBITMQ_URL": value,
                    }):
                        with self.assertRaises(RuntimeError) as caught:
                            load_worker(service)
                        self.assertNotIn("pass@", str(caught.exception))

    def test_rejects_unreviewed_runtime_environments(self):
        for environment in ("production", "staging", "", "prod"):
            with self.subTest(environment=environment):
                with patch.dict(os.environ, {
                    "KOLOVIBE_ENV": environment,
                    "KOLOVIBE_RABBITMQ_URL": "amqps://user:pass@rabbitmq:5671/vhost",
                }):
                    with self.assertRaisesRegex(RuntimeError, "blocked"):
                        load_worker("engagement")

    def test_validated_configuration_and_queue_isolation(self):
        fake_module = types.ModuleType("celery")
        fake_module.Celery = FakeCelery
        for service in ("engagement", "points"):
            with self.subTest(service=service):
                with patch.dict(sys.modules, {"celery": fake_module}):
                    with patch.dict(os.environ, {
                        "KOLOVIBE_ENV": "local",
                        "KOLOVIBE_RABBITMQ_URL": "amqps://user:pass@rabbitmq:5671/vhost",
                    }):
                        worker = load_worker(service)
                settings = worker.app.settings
                self.assertEqual(worker.app.name, "kolovibe-" + service)
                self.assertEqual(settings["task_default_queue"], "kolovibe." + service)
                self.assertEqual(settings["broker_use_ssl"]["cert_reqs"], ssl.CERT_REQUIRED)
                self.assertEqual(settings["accept_content"], ["json"])
                self.assertIsNone(settings["result_backend"])
                self.assertTrue(settings["task_acks_late"])
                self.assertTrue(settings["task_reject_on_worker_lost"])
                self.assertEqual(settings["worker_prefetch_multiplier"], 1)


if __name__ == "__main__":
    unittest.main()
