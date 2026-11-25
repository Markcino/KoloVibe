"""Structural guards for the Business service (Phase 6E): one definition of each shared rule, nothing unused.

Each of these was a real duplication before Phase 6E (the reason-code validator existed four times, the role tuples six
times, the cursor/limit spec five times). The guards keep a rule in the one module that owns it, so a future change to
the rule cannot be made in one copy and missed in another.
"""
import ast
import re
from pathlib import Path

from django.test import SimpleTestCase

SERVICE = Path(__file__).resolve().parents[1] / "service"
MODULES = {path.name: path.read_text() for path in sorted(SERVICE.glob("*.py")) if path.name != "__init__.py"}
TREES = {name: ast.parse(text) for name, text in MODULES.items()}
ROLES = {"viewer", "creator", "moderator", "administrator", "anonymous"}


class OneDefinitionTests(SimpleTestCase):
    def test_role_tuples_are_defined_only_in_the_entitlement_module(self):
        for name, tree in TREES.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Tuple, ast.BinOp)) and name != "authz.py":
                    literals = {c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
                    self.assertFalse(literals and literals <= ROLES, f"{name} defines its own role tuple at line {node.lineno}")

    def test_the_code_pattern_and_validator_exist_once(self):
        pattern = r'[a-z][a-z_]{2,39}'
        self.assertEqual([n for n, text in MODULES.items() if pattern in text], ["validation.py"])
        defined = [n for n, tree in TREES.items() for f in tree.body if isinstance(f, ast.FunctionDef) and f.name in ("_code", "code_text")]
        self.assertEqual(defined, ["validation.py"])

    def test_paged_operations_share_one_cursor_and_limit_spec(self):
        for name, text in MODULES.items():
            if name != "validation.py":
                self.assertNotIn('{"cursor": (lambda v: v, False), "limit": (lambda v: v, False)}', text, name)

    def test_no_module_carries_an_unused_import(self):
        for name, tree in TREES.items():
            imported = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update({(a.asname or a.name).split(".")[0]: node.lineno for a in node.names})
                elif isinstance(node, ast.ImportFrom):
                    imported.update({a.asname or a.name: node.lineno for a in node.names})
            used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.value.id for n in ast.walk(tree)
                                                                               if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
            reexported = {"inquiries", "listings", "ownership", "profiles", "reviews", "verification"} if name == "api.py" else set()
            unused = sorted(set(imported) - used - reexported - ({"models"} if name == "models.py" else set()))
            self.assertEqual(unused, [], f"{name} imports names it never uses")
