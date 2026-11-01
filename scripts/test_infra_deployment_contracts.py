"""Preflight invariants for the *unactivated* Oracle/RabbitMQ candidate."""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
BROKER = ROOT / "infra/swarm/staging.yml"
IMPLEMENTATION = ROOT / "docs/architecture/DOC-208_Oracle_VM_Implementation.mmd"
PORTS = ROOT / "docs/architecture/DOC-208_Oracle_Network_Ports.csv"


class InfrastructurePreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BROKER.read_text()
        cls.stack = yaml.safe_load(cls.source)

    def test_broker_is_private_and_uses_actual_encrypted_overlay(self):
        broker = self.stack["services"]["rabbitmq"]
        self.assertEqual(broker["networks"], ["broker_private"])
        self.assertEqual(self.stack["networks"]["broker_private"],
                         {"external": True, "name": "kolovibe_messaging"})
        self.assertNotIn("ports", broker)
        self.assertNotIn("privileged", broker)
        self.assertNotIn("network_mode", broker)

    def test_broker_requires_pinned_dhi_and_reviewed_capacity(self):
        broker = self.stack["services"]["rabbitmq"]
        self.assertIn("${RABBITMQ_DHI_IMAGE:?", broker["image"])
        self.assertIn("dhi.io/rabbitmq@sha256", broker["image"])
        limit = broker["deploy"]["resources"]["limits"]["memory"]
        self.assertIn("${RABBITMQ_MEMORY_LIMIT:?", limit)
        self.assertNotIn("1024M", self.source)
        self.assertEqual(broker["deploy"]["replicas"], 0)
        self.assertIn("node.labels.kolovibe.rabbitmq == true",
                      broker["deploy"]["placement"]["constraints"])

    def test_broker_secret_and_storage_boundaries(self):
        broker = self.stack["services"]["rabbitmq"]
        self.assertEqual(broker["volumes"], ["rabbitmq_data:/var/lib/rabbitmq"])
        for name in broker["secrets"]:
            self.assertEqual(self.stack["secrets"][name], {"external": True})
        self.assertEqual(broker["configs"][0]["target"], "/etc/rabbitmq/rabbitmq.conf")

    def test_reconciled_implementation_does_not_claim_third_vm_or_redis(self):
        diagram = IMPLEMENTATION.read_text()
        self.assertIn("Oracle VM1 - single Swarm manager and host ingress", diagram)
        self.assertIn("Oracle VM2 - Swarm worker", diagram)
        self.assertIn("RabbitMQ DHI", diagram)
        self.assertIn("cloudflared", diagram)
        self.assertNotIn("Redis", diagram)
        self.assertNotIn("3 Managers", diagram)
        self.assertIn("pending", diagram.lower())

    def test_network_register_distinguishes_verified_and_pending(self):
        ports = PORTS.read_text()
        self.assertIn("kolovibe_messaging", ports)
        self.assertIn("2377/TCP", ports)
        self.assertIn("7946/TCP+UDP", ports)
        self.assertIn("ESP protocol 50", ports)
        self.assertIn("pending", ports.lower())


if __name__ == "__main__":
    unittest.main()
