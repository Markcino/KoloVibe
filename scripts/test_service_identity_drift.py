"""Keep the eight copies of the service-identity code identical and the caller policy least-privilege."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("gateway", "identity", "creators", "content", "engagement", "points", "moderation", "audit", "business")
PRODUCERS = {"identity", "moderation", "creators", "content", "points", "business"}


def shared(path, kind):
    text = path.read_text()
    match = re.search(rf"^# BEGIN shared service-identity {kind}.*?^# END shared service-identity {kind}\n",
                      text, re.S | re.M)
    assert match, f"{path} lacks the shared {kind} block"
    return match.group(0)


def policy(service):
    tree = ast.parse((ROOT / "services" / service / "service" / "service_auth.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == "CALLER_PATHS":
            return ast.literal_eval(node.value)
    raise AssertionError(f"{service} has no CALLER_PATHS")


class ServiceIdentityDriftTests(unittest.TestCase):
    def test_verifier_signer_and_tests_are_identical_in_every_service(self):
        for label, name, kind in (("verifier", "service/service_auth.py", "verifier"),
                                  ("signer", "service/internal_client.py", "signer")):
            blocks = {service: shared(ROOT / "services" / service / name, kind) for service in SERVICES}
            self.assertEqual(len(set(blocks.values())), 1, f"{label} code drifted between services")
        for name in ("test_service_identity.py", "test_signing_keys.py"):
            copies = {service: (ROOT / "services" / service / "tests" / name).read_text() for service in SERVICES}
            self.assertEqual(len(set(copies.values())), 1, f"{name} drifted between services")

    def test_each_service_accepts_only_least_privilege_callers(self):
        policies = {service: policy(service) for service in SERVICES}
        self.assertEqual(policies["gateway"], {})
        for service in ("identity", "creators", "engagement", "points", "moderation"):
            self.assertEqual(set(policies[service]), {"gateway"}, service)
        self.assertEqual(set(policies["content"]), {"gateway", "moderation"})
        self.assertEqual(policies["content"]["moderation"], ("/internal/videos/moderation/",))
        self.assertEqual(policies["business"], {"gateway": ("/internal/probe", "/internal/business/")})
        self.assertEqual(set(policies["audit"]), PRODUCERS | {"gateway"})
        self.assertEqual(policies["audit"]["gateway"], ("/internal/probe", "/internal/audit/read"))
        for producer in PRODUCERS:
            self.assertEqual(policies["audit"][producer], ("/internal/security-events",))

    def test_no_service_names_itself_as_a_caller(self):
        for service in SERVICES:
            self.assertNotIn(service, policy(service))


if __name__ == "__main__":
    unittest.main()
