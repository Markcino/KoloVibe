"""Enforce review-worthy Bandit findings; retain low-severity findings in the artifact."""
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
findings = report.get("results", [])
blocking = [item for item in findings if item.get("issue_severity") in ("MEDIUM", "HIGH")]
print(f"Bandit: {len(findings)} total findings; {len(blocking)} medium/high")
for finding in blocking:
    print(f"{finding['filename']}:{finding['line_number']}: {finding['test_id']} {finding['issue_text']}")
if blocking:
    raise SystemExit(1)
