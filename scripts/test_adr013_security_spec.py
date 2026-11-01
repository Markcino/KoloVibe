"""Validate canonical ADR-013 contracts without treating staging code as approval."""

import csv
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs" / "architecture"
SPEC = ARCH / "ADR-013_Django_Native_Identity_Selection_2026-11-01.md"
API = ARCH / "DOC-205_OpenAPI_3_1_DRAFT.yaml"


def load_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class ProposedADR013DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = SPEC.read_text(encoding="utf-8")
        cls.api = yaml.safe_load(API.read_text(encoding="utf-8"))

    def test_policy_unapproved_and_safe_boundary(self):
        self.assertIn("Partially decided", self.spec)
        self.assertIn("ADR-012", self.spec)
        self.assertIn("not final ADR-013 approval", self.spec)
        self.assertIn("Do not mark it fully accepted", self.spec)

    def test_exact_policy_timeout_values_stated(self):
        challenge = self.api["components"]["schemas"]["MfaChallengeResponse"]
        self.assertEqual(challenge["properties"]["expires_in"]["const"], 300)
        self.assertEqual(challenge["properties"]["mfa_required"]["const"], True)
        self.assertFalse(challenge["additionalProperties"])

    def test_web_mobile_and_mfa_sections(self):
        for expected in ("TOTP", "recovery", "PostgreSQL", "CSRF", "SMTP"):
            self.assertIn(expected.lower(), self.spec.lower())

    def test_canonical_mfa_contract_is_gated_and_password_has_no_session(self):
        paths = self.api["paths"]
        challenge = paths["/auth/login"]["post"]["responses"]["202"]
        self.assertEqual(challenge["content"]["application/json"]["schema"]["$ref"],
                         "#/components/schemas/MfaChallengeResponse")
        mfa = paths["/auth/mfa/verify"]["post"]
        self.assertEqual(mfa["x-implementation"], "staging-gated")
        self.assertEqual(set(mfa["responses"]), {"200", "400", "401", "403", "429", "503"})
        self.assertNotIn("roles", self.api["components"]["schemas"]["RegisterRequest"]["properties"])
        self.assertEqual(self.api["components"]["securitySchemes"]["bearerAuth"]["bearerFormat"],
                         "Django-signed")

    def test_existing_selection_stays_partial(self):
        register = load_csv(ARCH / "DOC-207_ADR_Register.csv")
        decision = [row for row in register if row["ID"] == "ADR-013"]
        self.assertEqual(len(decision), 1)
        self.assertIn("Partially decided", decision[0]["Status"])
        self.assertIn("Django-native", decision[0]["Decision"])
        gates = load_csv(ARCH / "DOC-209_Gate_Criteria.csv")
        gate = next(row for row in gates if row["Gate_ID"] == "G-03")
        self.assertIn("BLOCKED", gate["Current_assessment"])

    def test_no_accidental_escaped_inline_markdown(self):
        self.assertNotIn("\\`", self.spec)
        self.assertNotIn("\\`", API.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
