"""Phase 6E: the Business contract, the Gateway, the Business service and the captured responses agree exactly.

DOC-205 is the one approved contract. This test reads all four sides and fails when any of them drifts:

* every declared Business operation has a Gateway route, and every Gateway Business route is declared;
* every route is behind the capability flag the contract names, and is not served at all while the flags are closed;
* the Gateway table and the service registry describe the same operations with the same authority rules
  (who may call, MFA, verified email, idempotency, public or signed-in);
* the contract declares every error status the service can return, and every query parameter the Gateway accepts;
* the real service answers captured for the Flutter app validate against the contract's response schemas;
* operations that appear only in the superseded 6A proposal are not routed anywhere.

The Gateway and the service are both a Django project called `service`, so each is read in its own process
(`probe_business_surface.py`). The reviewer and administrator console is checked in its own suite
(`apps/web_django/tests/test_business_contract_alignment.py`) against the same contract.
"""

import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from jsonschema import Draft202012Validator, FormatChecker
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "DOC-205_OpenAPI_3_1_DRAFT.yaml"
PROPOSAL = ROOT / "docs" / "architecture" / "business" / "BIZ-OpenAPI_3_1_PROPOSAL.yaml"
MATRIX = ROOT / "docs" / "security" / "phase6" / "BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md"
FIXTURES = ROOT / "apps" / "mobile" / "test" / "fixtures" / "business"
METHODS = ("get", "post", "put", "patch", "delete")
CUSTOMER = ["creator", "viewer"]
PRIVILEGED = ["administrator", "moderator"]
# Operations the app is allowed to lack a captured answer for, each with its reason.
NO_FIXTURE = {"member_remove": "the service refuses every caller until step-up exists (DR-BZ-33), so there is no success answer"}


def probe(side):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "probe_business_surface.py"), side],
                         capture_output=True, text=True, timeout=120, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def contract_operations(path=CONTRACT):
    """{(METHOD, path): operation} for every Business operation of a contract file."""
    spec = yaml.safe_load(path.read_text())
    found = {}
    for url, item in spec["paths"].items():
        for method, operation in item.items():
            if method in METHODS and (str(operation.get("x-capability", "")).startswith("business") or path != CONTRACT):
                found[(method.upper(), url)] = operation
    return spec, found


class BusinessContractReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.contract = contract_operations()
        cls.gateway, cls.service = probe("gateway"), probe("business")["operations"]
        cls.routed = {(method, route["path"]): name for route in cls.gateway["routes"]
                      for method, name in route["operations"].items()}
        cls.by_name = {name: key for key, name in cls.routed.items()}

    # ---- declared <-> implemented ---------------------------------------------------------------------------------
    def test_every_declared_operation_is_routed_and_every_route_is_declared(self):
        self.assertEqual(len(self.contract), 57, "the Business operation count changed; update the app, the console and this count")
        self.assertEqual(sorted(set(self.contract) - set(self.routed)), [], "declared but not served by the Gateway")
        self.assertEqual(sorted(set(self.routed) - set(self.contract)), [], "served by the Gateway but not declared")

    def test_every_route_is_behind_the_capability_the_contract_names_and_all_are_closed_by_default(self):
        for flag, routes in self.gateway["flags"].items():
            with self.subTest(flag):
                declared = sorted(f"{method} {path}" for (method, path), operation in self.contract.items()
                                  if operation["x-capability"] == flag)
                self.assertEqual(routes, declared)
        self.assertEqual(sum(len(routes) for routes in self.gateway["flags"].values()), 57)
        self.assertEqual(self.gateway["routes_when_closed"], 0, "a Business route is served while every flag is closed")

    def test_the_gateway_table_and_the_service_registry_hold_the_same_operations(self):
        self.assertEqual(set(self.gateway["operations"]), set(self.service))
        self.assertEqual(set(self.by_name), set(self.service), "a service operation has no route, or a route has no operation")

    def test_each_gateway_route_uses_the_method_its_table_entry_declares(self):
        for (method, _), name in self.routed.items():
            with self.subTest(name):
                self.assertEqual(self.gateway["operations"][name]["methods"], [method])

    # ---- authority ------------------------------------------------------------------------------------------------
    def test_the_gateway_and_the_service_agree_on_who_may_call_each_operation(self):
        for name, service in self.service.items():
            gateway = self.gateway["operations"][name]
            roles = sorted(role for role in service["roles"] if role != "anonymous")
            with self.subTest(name):
                self.assertEqual(gateway["verified_email"], service["verified_email"])
                if gateway["who"] == "public":
                    self.assertIn("anonymous", service["roles"])
                    self.assertFalse(service["mfa"])
                elif gateway["who"] == "privileged":
                    self.assertTrue(service["mfa"], "a privileged route must demand fresh MFA at the service too")
                    self.assertTrue(set(roles) <= set(PRIVILEGED), roles)
                else:
                    self.assertEqual((roles, service["mfa"]), (CUSTOMER, False))

    def test_the_contract_states_the_same_authority_rules_as_the_service(self):
        for key, operation in self.contract.items():
            name = self.routed[key]
            service = self.service[name]
            roles = sorted(role for role in service["roles"] if role != "anonymous")
            declared_key = any(p.get("name") == "Idempotency-Key" and p.get("required") for p in operation.get("parameters", []))
            with self.subTest(name):
                if "anonymous" in service["roles"]:
                    self.assertEqual(operation.get("security"), [], "a public operation must be declared anonymous")
                    self.assertIn(sorted(operation.get("x-required-roles", [])), ([], sorted(CUSTOMER + PRIVILEGED)))
                else:
                    self.assertNotEqual(operation.get("security"), [], "a protected operation is declared anonymous")
                    self.assertEqual(sorted(operation["x-required-roles"]), roles)
                self.assertEqual(bool(operation.get("x-mfa-required")), service["mfa"])
                self.assertEqual(declared_key, service["idempotent"], "Idempotency-Key declaration differs from the service")

    def test_every_operation_names_a_row_of_the_authorization_matrix(self):
        """One matrix row may govern several operations (the same rule), but every reference must be a real row."""
        rows = set(re.findall(r"^\| (BZ-AZ-\d+) \|", MATRIX.read_text(), re.M))
        self.assertGreaterEqual(len(rows), 50)
        for key, operation in self.contract.items():
            with self.subTest(self.routed[key]):
                self.assertIn(operation.get("x-authz-ref"), rows)

    # ---- errors and inputs ----------------------------------------------------------------------------------------
    def test_the_contract_declares_every_status_the_service_can_answer(self):
        for key, operation in self.contract.items():
            name = self.routed[key]
            service, gateway = self.service[name], self.gateway["operations"][name]
            public = "anonymous" in service["roles"]
            needed = {"503"}
            if not public:
                needed.add("401")
            if not public and (service["mfa"] or service["roles"] != ["viewer", "creator"]):
                needed.add("403")
            if service["verified_email"]:
                needed.add("403")
            if service["budget"] or public:
                needed.add("429")
            if "{" in key[1] and not key[1].startswith("/admin/"):
                needed.add("404")
            if key[0] != "GET" or gateway["query"]:
                needed.add("400")
            with self.subTest(name):
                self.assertEqual(sorted(needed - set(operation["responses"])), [], "an answer the service gives is not declared")

    def test_every_query_parameter_the_gateway_accepts_is_declared_and_no_other_is_declared(self):
        for key, operation in self.contract.items():
            declared = sorted(p["name"] for p in operation.get("parameters", []) if p["in"] == "query")
            with self.subTest(self.routed[key]):
                self.assertEqual(declared, sorted(self.gateway["operations"][self.routed[key]]["query"]))

    # ---- responses --------------------------------------------------------------------------------------------------
    def fixtures(self):
        names = sorted(self.by_name, key=len, reverse=True)
        for path in sorted(FIXTURES.glob("*.json")):
            if not path.stem.startswith("_"):
                yield path.stem, next(n for n in names if path.stem == n or path.stem.startswith(n + "_")), json.loads(path.read_text())

    def test_the_real_service_answers_the_app_depends_on_match_the_contract_schemas(self):
        seen = set()
        for stem, name, captured in self.fixtures():
            method, path = self.by_name[name]
            declared = self.contract[(method, path)]["responses"]
            with self.subTest(stem):
                self.assertIn(str(captured["status"]), declared, "the service answered a status the contract does not declare")
                content = declared[str(captured["status"])].get("content", {}).get("application/json")
                if content is None:  # an error answer: bounded detail and an optional code, never anything else
                    self.assertTrue({"detail"} <= set(captured["body"]) <= {"detail", "code"}, captured["body"])
                    continue
                Draft202012Validator({**content["schema"], "components": self.spec["components"]},
                                     format_checker=FormatChecker()).validate(captured["body"])
                seen.add(name)
        app_facing = {name for (method, path), name in self.routed.items()
                      if not path.startswith(("/moderation/", "/admin/"))}
        self.assertEqual(sorted(app_facing - seen - set(NO_FIXTURE)), [], "an app-facing operation has no validated answer")

    # ---- obsolete -----------------------------------------------------------------------------------------------------
    def test_operations_only_the_superseded_proposal_describes_are_not_routed(self):
        _, proposal = contract_operations(PROPOSAL)
        obsolete = sorted(set(proposal) - set(self.contract))
        self.assertGreaterEqual(len(obsolete), 11, "the proposal and the contract no longer differ; review this test")
        served = set(self.routed)
        normal = lambda path: re.sub(r"\{[^}]+\}", "{}", path)
        served_shapes = {(method, normal(path)) for method, path in served}
        for method, path in obsolete:
            with self.subTest(f"{method} {path}"):
                self.assertNotIn((method, normal(path)), served_shapes)


if __name__ == "__main__":
    unittest.main()
