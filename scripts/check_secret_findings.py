"""Fail CI on secrets, except narrowly verified generated non-secret identifiers.

The only allowed exceptions are hex-entropy detections on recognized metadata
fields. The underlying detect-secrets scan still covers every tracked file and
all other detector types; new fields or locations remain blocking findings.
"""
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r'^\s*"sha256"\s*:\s*"[a-fA-F0-9]{64}"\s*,?\s*$')
REVISION = re.compile(r'^\s*revision:\s*"[a-fA-F0-9]{40}"\s*$')
BLUEPRINT = re.compile(r'^\s*BlueprintIdentifier\s*=\s*"[a-fA-F0-9]{24}"\s*$')

SAFE_FIELDS = {
    "docs/mobile-asset-manifest.json": HEX64,
    "apps/mobile/.metadata": REVISION,
    "apps/mobile/ios/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme": BLUEPRINT,
}


def is_known_nonsecret(filename, finding, repository_root):
    """Allow only a hex detector result on the exact expected generated field."""
    if finding.get("type") != "Hex High Entropy String":
        return False
    field_pattern = SAFE_FIELDS.get(filename)
    if field_pattern is None:
        return False
    line_number = finding.get("line_number")
    if type(line_number) is not int or line_number < 1:
        return False
    try:
        lines = (repository_root / filename).read_text(encoding="utf-8").splitlines()
        line = lines[line_number - 1]
    except (OSError, IndexError, UnicodeError):
        return False
    return bool(field_pattern.fullmatch(line))


def main(report_path, repository_root=Path(".")):
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    findings = report.get("results")
    if not isinstance(findings, dict):
        raise SystemExit("Invalid detect-secrets report: missing results map")
    blocked = {}
    ignored = 0
    for filename, entries in findings.items():
        if not isinstance(filename, str) or not isinstance(entries, list):
            raise SystemExit("Invalid detect-secrets report entry")
        for finding in entries:
            if not isinstance(finding, dict) or not is_known_nonsecret(
                filename, finding, repository_root
            ):
                blocked.setdefault(filename, []).append(finding)
            else:
                ignored += 1
    if blocked:
        print("Potential secrets require review:", *blocked.keys(), sep="\n - ")
        raise SystemExit(1)
    print(
        "Secret scan passed; recognized generated non-secret identifiers:",
        ignored,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_secret_findings.py <report.json>")
    main(sys.argv[1])
