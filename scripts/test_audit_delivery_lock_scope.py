"""Regression guard for least-privilege audit delivery row locking.

All six delivery commands join immutable event rows for reading. The runtime
roles cannot UPDATE the event tables, so PostgreSQL must lock only the mutable
AuditDelivery row rather than the full join.
"""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    "services/identity/service/management/commands/deliver_security_audit.py",
    "services/points/service/management/commands/deliver_audit_events.py",
    "services/moderation/service/management/commands/deliver_audit_events.py",
    "services/business/service/management/commands/deliver_audit_events.py",
    "services/creators/service/management/commands/deliver_audit_events.py",
    "services/content/service/management/commands/deliver_audit_events.py",
)


class AuditDeliveryLockScopeTests(unittest.TestCase):
    def test_delivery_commands_lock_only_self(self):
        for relative_path in COMMANDS:
            with self.subTest(command=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                tree = ast.parse(source, filename=relative_path)
                calls = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "select_for_update"
                ]
                self.assertEqual(len(calls), 1, "Expected one explicit audit delivery lock")
                call = calls[0]
                self.assertFalse(call.args, "No positional locking arguments")
                self.assertEqual(
                    len(call.keywords), 1,
                    "Unexpected audit locking options may widen the row locks",
                )
                self.assertEqual(call.keywords[0].arg, "of")
                value = ast.literal_eval(call.keywords[0].value)
                self.assertEqual(value, ("self",))


if __name__ == "__main__":
    unittest.main()
