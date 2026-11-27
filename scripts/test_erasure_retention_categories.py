"""Identity's retention-policy vocabulary equals what each participating service can report as retained (ADR-020)."""
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("identity_retention_policy",
                                               ROOT / "services/identity/service/retention_policy.py")
retention_policy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retention_policy)  # stdlib only; loaded by path so no `service` package is imported


def reported(service):
    """Category names a service's privacy module can put in `retained`: keys of its checks/RETAINED tables and
    names it appends directly."""
    text = (ROOT / "services" / service / "service/privacy.py").read_text()
    names = set(re.findall(r'retained\.append\("([a-z][a-z0-9_]*)"\)', text))
    names |= set(re.findall(r'^\s*"([a-z][a-z0-9_]*)":\s*(?:[A-Z]\w*\.objects|authz\.)', text, re.M))
    for table in re.findall(r'^RETAINED = \{([^}]*)\}', text, re.M):
        names |= set(re.findall(r'"([a-z][a-z0-9_]*)":', table))
    return names


class RetentionVocabularyTests(unittest.TestCase):
    def test_every_reported_category_is_either_evidence_or_unfinished_work(self):
        for service in ("engagement", "creators", "moderation", "content", "business"):
            with self.subTest(service):
                self.assertEqual(reported(service),
                                 retention_policy.EVIDENCE_CATEGORIES[service]
                                 | retention_policy.NEVER_COMPATIBLE.get(service, frozenset()))

    def test_unfinished_work_is_never_evidence(self):
        for service, names in retention_policy.NEVER_COMPATIBLE.items():
            self.assertFalse(names & retention_policy.EVIDENCE_CATEGORIES[service])


if __name__ == "__main__":
    unittest.main()
