"""Break CI on secret detections rather than merely uploading a report."""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
report = json.loads(path.read_text())
findings = {k: v for k, v in report.get("results", {}).items() if v}
if findings:
    print("Potential secrets detected in:", *findings.keys(), sep="\n - ")
    raise SystemExit(1)
print("No potential secrets detected by configured detector set")
