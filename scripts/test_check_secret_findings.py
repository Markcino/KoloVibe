"""Regression tests for context-aware detection, including fail-closed cases."""
import json
import tempfile
import unittest
from pathlib import Path

from check_secret_findings import main


class SecretFindingChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def check(self, path, line, kind="Hex High Entropy String", filename=None):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(line + "\n", encoding="utf-8")
        report = self.root / "findings.json"
        report.write_text(json.dumps({"results": {
            filename or path: [{"type": kind, "line_number": 1}]
        }}), encoding="utf-8")
        main(report, self.root)

    def test_flutter_revision_allowed(self):
        self.check("apps/mobile_flutter/.metadata", '  revision: "' + "a" * 40 + '"')

    def test_xcode_blueprint_allowed(self):
        self.check(
            "apps/mobile_flutter/ios/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme",
            '  BlueprintIdentifier = "' + "A" * 24 + '"',
        )

    def test_asset_checksum_allowed(self):
        self.check("docs/mobile-asset-manifest.json", '    "sha256": "' + "f" * 64 + '",')

    def test_actual_secret_on_allowlisted_path_fails(self):
        with self.assertRaises(SystemExit) as context:
            self.check("docs/mobile-asset-manifest.json", '    "api_token": "' + "f" * 64 + '",')
        self.assertEqual(context.exception.code, 1)

    def test_new_detector_type_on_metadata_fails(self):
        with self.assertRaises(SystemExit) as context:
            self.check("apps/mobile_flutter/.metadata", 'revision: "' + "a" * 40 + '"',
                       kind="AWS Access Key")
        self.assertEqual(context.exception.code, 1)

    def test_unrecognized_file_fails(self):
        with self.assertRaises(SystemExit) as context:
            self.check("services/identity/settings.py", 'token = "' + "a" * 40 + '"')
        self.assertEqual(context.exception.code, 1)

    def test_invalid_report_fails_closed(self):
        report = self.root / "findings.json"
        report.write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit):
            main(report, self.root)


if __name__ == "__main__":
    unittest.main()
