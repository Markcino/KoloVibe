"""The gateway's public surface is default-deny against the API contract.

DOC-205 declares which operations are anonymous (`security: []`). Every other operation, on every gateway route,
must reject a request that carries no credential, and must do so before any internal service is contacted. A new
gateway route must also be declared in DOC-205, so an undeclared route cannot appear unnoticed.
"""

import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "DOC-205_OpenAPI_3_1_DRAFT.yaml"
API_PREFIX = "/api/v1"
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
# Routes the contract deliberately does not declare. Each needs a stated reason.
UNDECLARED = {
    "/health/live": "liveness probe; declared in DOC-205 without the API prefix",
    "/internal/probe": "private liveness probe; the signed-peer middleware rejects public callers (403)",
    "/videos": "legacy unprefixed alias of GET /api/v1/videos; kept for compatibility (staging PUBLIC allowlist)",
}
# Contract paths the gateway does not serve.
NOT_GATEWAY = {"/health/ready", "/health/live"}


def normalise(path):
    return re.sub(r"\{[^}/]+\}", "{id}", path)


def contract():
    spec = yaml.safe_load(CONTRACT.read_text())
    operations, anonymous = set(), set()
    for path, item in spec["paths"].items():
        if path.startswith("/internal/"):
            continue
        for method, operation in item.items():
            if method in HTTP_METHODS:
                key = (method.upper(), normalise(path))
                operations.add(key)
                if operation.get("security") == []:
                    anonymous.add(key)
    return operations, anonymous


def probe():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "probe_gateway_anonymous.py")],
                         capture_output=True, text=True, timeout=120, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


class GatewayRouteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.operations, cls.anonymous = contract()
        cls.routes = probe()

    def public_path(self, route):
        return route[len(API_PREFIX):] if route.startswith(API_PREFIX + "/") else route

    def test_every_gateway_route_is_declared_in_the_contract(self):
        declared = {path for _, path in self.operations}
        for route in self.routes:
            if route in UNDECLARED:
                continue
            with self.subTest(route):
                self.assertTrue(route.startswith(API_PREFIX + "/"), f"{route} is outside {API_PREFIX}")
                self.assertTrue(self.public_path(route) in declared, f"{route} is not declared in DOC-205")

    def test_contract_paths_are_served_by_the_gateway(self):
        served = {self.public_path(route) for route in self.routes}
        for _, path in sorted(self.operations):
            if path in NOT_GATEWAY:
                continue
            with self.subTest(path):
                self.assertTrue(path in served, f"DOC-205 declares {path} but the gateway has no such route")

    def test_exemptions_are_current(self):
        for route in UNDECLARED:
            self.assertTrue(route in self.routes, f"{route} no longer exists; remove its exemption")

    def test_credentialless_requests_are_rejected_before_any_internal_call(self):
        """Operations the contract does not mark anonymous never reach an internal service without a credential."""
        for route, results in self.routes.items():
            if route in UNDECLARED:
                continue
            for method, outcome in results.items():
                if (method, self.public_path(route)) in self.anonymous:
                    continue
                with self.subTest(f"{method} {route}"):
                    self.assertIn(outcome["status"], {401, 404, 405},
                                  f"{method} {route} answered {outcome['status']} without a credential")
                    self.assertEqual(outcome["internal_calls"], 0,
                                     f"{method} {route} reached an internal service without a credential")

    def test_every_non_anonymous_route_demands_authentication(self):
        """At least one method of each protected route answers 401, so a route cannot be silently open or dead."""
        for route, results in self.routes.items():
            path = self.public_path(route)
            if route in UNDECLARED or all((m, path) in self.anonymous for m in results if (m, path) in self.operations):
                continue
            declared = [m for m in results if (m, path) in self.operations and (m, path) not in self.anonymous]
            if not declared:
                continue
            with self.subTest(route):
                self.assertTrue(any(results[m]["status"] == 401 for m in declared),
                                f"no declared protected method of {route} answered 401: "
                                f"{ {m: results[m]['status'] for m in declared} }")

    def test_declared_anonymous_operations_are_a_known_short_list(self):
        """Widening the anonymous surface must be a visible change to this list."""
        self.assertEqual(
            {f"{m} {p}" for m, p in self.anonymous},
            {"POST /auth/register", "POST /auth/verification/resend", "POST /auth/verify",
             "POST /auth/password/reset-request", "POST /auth/password/reset", "POST /auth/login",
             "POST /auth/mfa/verify", "POST /auth/refresh", "POST /auth/logout", "GET /creators/search",
             "GET /creators/{id}", "GET /videos", "GET /videos/{id}", "GET /app/compatibility",
             "GET /health/live", "GET /health/ready", "POST /auth/moderator-invitations/setup",
             "POST /auth/moderator-invitations/complete",
             "GET /business-categories", "GET /businesses", "GET /businesses/{id}",
             "GET /businesses/{id}/reviews"})


if __name__ == "__main__":
    unittest.main()
