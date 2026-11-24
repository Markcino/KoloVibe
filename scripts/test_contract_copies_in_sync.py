"""Response validators the web console and the gateway both apply must not drift apart.

The web console is a separate deployable that consumes the gateway's API and must reject malformed responses
independently, so it keeps its own copy of the validators rather than importing gateway code. Identical copies are
therefore guarded here (the same pattern as the service-identity drift test): change both or neither.
"""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "services" / "gateway" / "service"
WEB = ROOT / "apps" / "web_django" / "web"
IDENTICAL_MODULES = ("invitation_contracts.py", "reviewer_contracts.py")
SHARED_FUNCTIONS_MODULE = "admin_contracts.py"


def functions(path):
    source = path.read_text()
    return {node.name: ast.get_source_segment(source, node)
            for node in ast.parse(source).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


class ContractCopiesTests(unittest.TestCase):
    def test_whole_module_copies_are_identical(self):
        for name in IDENTICAL_MODULES:
            with self.subTest(name):
                self.assertEqual((GATEWAY / name).read_text(), (WEB / name).read_text(),
                                 f"{name} differs between the gateway and the web console; update both together")

    def test_functions_defined_in_both_admin_contract_modules_are_identical(self):
        gateway, web = functions(GATEWAY / SHARED_FUNCTIONS_MODULE), functions(WEB / SHARED_FUNCTIONS_MODULE)
        common = set(gateway) & set(web)
        self.assertTrue(common, "the two admin contract modules no longer share validators")
        for name in sorted(common):
            with self.subTest(name):
                self.assertEqual(gateway[name], web[name], f"{name} differs between gateway and web")

    def test_the_web_only_validators_are_the_only_difference(self):
        """A validator moving between the copies must be a deliberate, visible change."""
        gateway, web = functions(GATEWAY / SHARED_FUNCTIONS_MODULE), functions(WEB / SHARED_FUNCTIONS_MODULE)
        self.assertEqual(set(gateway) - set(web), set())
        self.assertEqual(set(web) - set(gateway),
                         {"valid_candidate", "valid_creator_summary", "valid_pending_applications", "valid_outstanding_invitations", "_uuid"})


if __name__ == "__main__":
    unittest.main()
