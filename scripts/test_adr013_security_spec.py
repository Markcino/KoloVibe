"""Validate draft ADR-013 references without treating proposed policy as approved."""

import csv
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs" / "architecture"
SPEC = ARCH / "ADR-013_Client_Authentication_and_Session_Security_v1.0_DRAFT.md"
API = ARCH / "ADR-013_DOC-205_Proposed_Contract_Delta_v1.0_DRAFT.md"
MATRIX = ARCH / "ADR-013_DOC-206_Verification_Matrix_v1.0_DRAFT.csv"


def load_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class ProposedADR013DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = SPEC.read_text(encoding="utf-8")
        cls.api = API.read_text(encoding="utf-8")
        cls.matrix = load_csv(MATRIX)

    def test_spec_has_complete_numbered_sections(self):
        sections = re.findall(r"^## (\d+)\.", self.spec, flags=re.MULTILINE)
        self.assertEqual(sections, [str(n) for n in range(1, 21)])

    def test_policy_unapproved_and_safe_boundary(self):
        self.assertIn("DRAFT — PENDING FORMAL APPROVAL", self.spec)
        self.assertIn("DO NOT MODIFY PRODUCTION", self.spec)
        self.assertIn("ADR-012", self.spec)
        self.assertIn("ADR-020", self.spec)
        self.assertIn("No production settings", self.spec)
        self.assertIn("NOT RUN", self.spec)

    def test_exact_policy_timeout_values_stated(self):
        for expected in ("300 seconds", "30 days absolute", "7 days",
                         "30 minutes idle", "8 hours absolute",
                         "15 minutes idle", "4 hours absolute",
                         "within 5 minutes", "15 minutes"):
            self.assertIn(expected, self.spec)

    def test_web_mobile_and_mfa_sections(self):
        for expected in ("WebAuthn", "TOTP", "Argon2id", "SameSite=Lax",
                         "SessionMiddleware", "flutter_secure_storage",
                         "PostgreSQL", "rate limit", "signed",
                         "revoke all", "CSRF"):
            self.assertIn(expected.lower(), self.spec.lower())

    def test_api_delta_does_not_claim_existing_routes_modified(self):
        self.assertIn("NO BASELINE CHANGE", self.api)
        self.assertIn("bearerFormat: JWT", self.api)
        self.assertIn("Django-signed", self.api)
        self.assertIn("NOT IMPLEMENTED", self.api)
        self.assertIn("DOC-205", self.api)
        self.assertIn("Do not", self.api)

    def test_matrix_has_unique_unexecuted_proposed_cases(self):
        self.assertEqual(len(self.matrix), 45)
        self.assertEqual(
            [row["Test_ID"] for row in self.matrix],
            [f"ADR013-V{n:02d}" for n in range(1, 46)],
        )
        self.assertTrue(all(row["Execution_Status"] == "NOT RUN" for row in self.matrix))
        self.assertTrue(all(row["Required_Evidence"] for row in self.matrix))

    def test_matrix_refs_exist_in_historical_controls(self):
        controls = {row["ID"] for row in load_csv(ARCH / "DOC-206_Control_Verification_Matrix.csv")}
        threats = {row["ID"] for row in load_csv(ARCH / "DOC-203_STRIDE_Risk_Register.csv")}
        for row in self.matrix:
            with self.subTest(case=row["Test_ID"]):
                self.assertTrue(set(row["DOC206_Control"].split(";")) <= controls)
                self.assertTrue(set(row["DOC203_Threat"].split(";")) <= threats)

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
        self.assertNotIn("\\`", self.api)


if __name__ == "__main__":
    unittest.main()
