"""Release Android manifest must reach the HTTPS API while excluding app data from backups."""

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


MAIN = Path(__file__).resolve().parents[1] / "apps" / "mobile" / "android" / "app" / "src" / "main"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class AndroidManifestTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(MAIN / "AndroidManifest.xml").getroot()
        self.app = self.root.find("application")

    def test_release_manifest_declares_internet_permission(self):
        names = [node.get(ANDROID + "name") for node in self.root.findall("uses-permission")]
        self.assertIn("android.permission.INTERNET", names)

    def test_backup_and_cleartext_are_disabled(self):
        self.assertEqual(self.app.get(ANDROID + "allowBackup"), "false")
        self.assertEqual(self.app.get(ANDROID + "usesCleartextTraffic"), "false")

    def test_network_config_forbids_cleartext_and_user_certificates(self):
        self.assertEqual(self.app.get(ANDROID + "networkSecurityConfig"), "@xml/network_security_config")
        config = ET.parse(MAIN / "res" / "xml" / "network_security_config.xml").getroot()
        base = config.find("base-config")
        self.assertEqual(base.get("cleartextTrafficPermitted"), "false")
        self.assertEqual([c.get("src") for c in base.iter("certificates")], ["system"])

    def test_data_extraction_rules_exclude_every_domain(self):
        self.assertEqual(self.app.get(ANDROID + "dataExtractionRules"), "@xml/data_extraction_rules")
        rules = ET.parse(MAIN / "res" / "xml" / "data_extraction_rules.xml").getroot()
        for section in ("cloud-backup", "device-transfer"):
            excluded = {node.get("domain") for node in rules.find(section).findall("exclude")}
            self.assertEqual(excluded, {"root", "file", "database", "sharedpref", "external"})
            self.assertIsNone(rules.find(section).find("include"))


if __name__ == "__main__":
    unittest.main()
