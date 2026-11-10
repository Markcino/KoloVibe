"""Cross-check the approved ADR-013 design and open verification across current registers."""

import csv
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs" / "architecture"
ENG = ROOT / "docs" / "engineering"


def matching_record(path, key, value):
    with path.open(newline="", encoding="utf-8") as handle:
        matches = [row for row in csv.DictReader(handle) if row.get(key) == value]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {value} record in {path}, found {len(matches)}")
    return matches[0]


class IdentityDecisionConsistencyTests(unittest.TestCase):
    def test_adr_register_records_design_approval_and_open_verification(self):
        row = matching_record(ARCH / "DOC-207_ADR_Register.csv", "ID", "ADR-013")
        self.assertIn("Design approved", row["Status"])
        self.assertIn("implementation and verification open", row["Status"])
        self.assertIn("Django-native", row["Decision"])

    def test_open_decision_logs_preserve_remaining_work(self):
        a = matching_record(ARCH / "DOC-207_Open_Decision_Log.csv",
                            "ADR_ID", "ADR-013")
        b = matching_record(ARCH / "DOC-209_Consolidated_Open_Decisions.csv",
                            "ID", "ADR-013")
        self.assertEqual(a["Current_status"], b["Status"])
        self.assertIn("verification open", a["Current_status"])

    def test_stage3_client_authority_not_misread_as_workload_identity(self):
        row = matching_record(ENG / "Stage3_Open_Decisions.csv",
                              "Decision", "OD-01")
        self.assertIn("client design approved", row["Status"])
        self.assertIn("workload", row["Status"])
        self.assertIn("pending", row["Status"])

    def test_governance_gate_remains_blocked(self):
        row = matching_record(ARCH / "DOC-209_Gate_Criteria.csv", "Gate_ID", "G-03")
        self.assertIn("BLOCKED", row["Current_assessment"])

    def test_historical_selection_points_to_approved_design(self):
        record = (ARCH / "ADR-013_Django_Native_Identity_Selection_2026-11-01.md").read_text()
        for phrase in ("Django-native", "ADR-012", "session", "MFA",
                       "refresh", "revocation", "ADR-013_Client_Authentication_and_Session_Security_v1.0_APPROVED.md"):
            self.assertIn(phrase.lower(), record.lower())

    def test_stage3_feature_gate_remains_open(self):
        current = (ENG / "Stage3_Current_Status.md").read_text()
        roadmap = (ENG / "API_Test_Deployment_Roadmap.md").read_text()
        self.assertIn("OD-01", current)
        self.assertIn("verified ADR-013 session/MFA implementation", roadmap)
        self.assertIn("Keep privileged APIs disabled", roadmap)


if __name__ == "__main__":
    unittest.main()
