"""Preflight invariants for the *unactivated* Oracle/RabbitMQ candidate."""

from pathlib import Path
import re
import sys
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "ops"))
import kolovibe_cluster as cluster  # noqa: E402
import validate_staging_stack as validator  # noqa: E402

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
        self.assertEqual(broker["deploy"]["placement"]["constraints"], [
            "node.labels.kolovibe.workloads == true",
            "node.labels.kolovibe.rabbitmq == true"])
        for service in ("gateway", "identity", "content", "creators",
                        "engagement", "points", "moderation", "audit"):
            self.assertEqual(
                self.stack["services"][service]["deploy"]["placement"]["constraints"],
                ["node.labels.kolovibe.workloads == true"])
            self.assertEqual(self.stack["services"][service]["deploy"]["replicas"], 0)

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


class PlacementProfileConsistencyTests(unittest.TestCase):
    """The label-based stack file, the AWS tool profile and the README must tell one story."""

    @classmethod
    def setUpClass(cls):
        cls.source = BROKER.read_text()
        cls.readme = (ROOT / "infra/swarm/README.md").read_text()
        cls.aws = cluster.AWS_STAGING

    def test_stack_file_declares_itself_oracle_placement_and_warns_off_aws(self):
        header = self.source.split("x-environment:")[0]
        self.assertIn("PLACEMENT PROFILE: oracle-staging only", header)
        self.assertIn("Do not `docker stack deploy` this file on AWS", header)

    def test_validator_accepts_oracle_and_refuses_aws_and_unknown_profiles_explicitly(self):
        stack = yaml.safe_load(self.source)
        with self.assertRaisesRegex(ValueError, "aws-staging profile of scripts/ops/kolovibe_cluster.py"):
            validator.validate(stack, "aws-staging")
        with self.assertRaisesRegex(ValueError, "Unknown placement profile"):
            validator.validate(stack, "guess")
        self.assertEqual(set(validator.PROFILES), set(cluster.PROFILES))

    def test_aws_profile_pins_by_hostname_and_never_needs_labels(self):
        self.assertEqual(self.aws.worker_constraint, "node.hostname==" + self.aws.worker_host)
        self.assertFalse(self.aws.broker_needs_label)
        self.assertNotIn("node.labels", self.aws.worker_constraint)
        for constraint in yaml.safe_load(self.source)["x-deploy"]["placement"]["constraints"]:
            self.assertNotEqual(constraint, self.aws.worker_constraint)

    def test_readme_table_states_the_same_aws_pin_and_hosts_as_the_tool(self):
        row = next(line for line in self.readme.splitlines() if line.startswith("| Worker pin every service must carry"))
        self.assertIn("`" + self.aws.worker_constraint + "`", row)
        hosts = next(line for line in self.readme.splitlines() if line.startswith("| Manager / worker hostname"))
        self.assertIn("`%s` / `%s`" % (self.aws.manager_host, self.aws.worker_host), hosts)
        self.assertTrue(re.search(r"AWS .*no (Swarm )?(node )?labels", self.readme, re.I | re.S))


if __name__ == "__main__":
    unittest.main()
