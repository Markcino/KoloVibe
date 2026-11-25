"""Phase 6E: every request the Business console can make is a declared, privileged, MFA-gated DOC-205 operation.

The console is a separate deployable. It keeps its own routing tables and response validators, so they are compared
here with the contract (and with the vocabulary the contract gives decisions and scopes) instead of being trusted.
"""

from pathlib import Path
import re
import unittest

import yaml

from web import business_contracts as contracts
from web import business_views as views

CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "DOC-205_OpenAPI_3_1_DRAFT.yaml"
SOURCE = Path(views.__file__).read_text()
PRIVILEGED = ["administrator", "moderator"]


def declared():
    spec = yaml.safe_load(CONTRACT.read_text())
    operations = {}
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method in ("get", "post", "put", "patch", "delete") and str(operation.get("x-capability", "")).startswith("business"):
                operations[(method.upper(), re.sub(r"\{[^}]+\}", "{}", path))] = operation
    return spec, operations


def console_requests():
    """(method, path template, who) for every gateway call the console code can make."""
    found = set()
    for kind, queue in views.QUEUES.items():
        found.add(("GET", queue["path"] + "", "queue"))
        found.add(("GET", queue["path"] + "/{}", "detail"))
        for op in views.OPERATIONS[kind].values():
            found.add(("POST", queue["path"] + "/{}" + op["path"], "decision"))
    found |= {("GET", "/business-categories", "categories"), ("PUT", "/admin/business-categories/{}", "category"),
              ("PUT", "/admin/business-reviewer-grants", "grant"), ("PUT", "/admin/business-registration-grants/{}", "grant")}
    return found


class ConsoleContractAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.operations = declared()

    def test_every_console_request_is_a_declared_operation(self):
        for method, path, what in sorted(console_requests()):
            with self.subTest(f"{method} {path}"):
                self.assertIn((method, path), self.operations, f"the console can send an undeclared {what} request")

    def test_the_source_still_contains_the_four_literal_paths_this_test_assumes(self):
        for literal in ('"/business-categories"', 'f"/admin/business-categories/{slug}"', '"/admin/business-reviewer-grants"',
                        'f"/admin/business-registration-grants/{account}"'):
            self.assertIn(literal, SOURCE)

    def test_every_privileged_console_request_is_mfa_gated_and_limited_to_reviewers_or_administrators(self):
        for method, path, what in sorted(console_requests()):
            if (method, path) == ("GET", "/business-categories"):
                continue  # the public category list, read with the reviewer's own token only to fill a menu
            operation = self.operations[(method, path)]
            with self.subTest(f"{method} {path}"):
                self.assertEqual(operation["x-capability"], "business_review_admin")
                self.assertTrue(operation.get("x-mfa-required"))
                # administration is administrator-only; the moderation queues are for reviewers and administrators
                self.assertEqual(sorted(operation["x-required-roles"]), ["administrator"] if path.startswith("/admin/") else PRIVILEGED)
                if method != "GET":
                    self.assertTrue(any(p.get("name") == "Idempotency-Key" and p.get("required") for p in operation["parameters"]),
                                    "a console write must carry an Idempotency-Key")

    def test_the_console_offers_exactly_the_decisions_and_scopes_the_contract_defines(self):
        schemas = self.spec["components"]["schemas"]
        self.assertEqual(set(contracts.VERIFICATION_DECISIONS), set(schemas["VerificationDecision"]["properties"]["decision"]["enum"]))
        self.assertEqual(set(contracts.PROFILE_DECISIONS), set(schemas["ProfileDecision"]["properties"]["decision"]["enum"]))
        self.assertEqual(set(contracts.REPORT_DECISIONS), set(schemas["BusinessReportDecision"]["properties"]["decision"]["enum"]))
        self.assertEqual(set(contracts.SCOPES), set(schemas["BusinessReviewerGrant"]["properties"]["scope"]["enum"]))
        self.assertEqual(contracts.CODE.pattern, schemas["VerificationDecision"]["properties"]["reason_code"]["pattern"].strip("^$"))

    def test_the_console_makes_no_request_for_an_operation_that_belongs_to_the_app(self):
        """DR-BZ-21: owners, staff and customers use the app. The console never calls an owner or customer operation."""
        for method, path, _ in console_requests():
            self.assertTrue(path.startswith(("/moderation/", "/admin/", "/business-categories")), path)


if __name__ == "__main__":
    unittest.main()
