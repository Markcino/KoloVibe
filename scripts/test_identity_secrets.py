from pathlib import Path
import unittest

from scripts.validate_identity_secrets import CONFIG_FILES, SECRET_FILES, secret_environment


class IdentitySecretTests(unittest.TestCase):
    def test_missing_secrets_fail_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "Missing protected identity"):
            with secret_environment({}):
                self.fail("Missing secrets were accepted")

    def test_private_files_are_removed_after_validation_or_failure(self):
        values = {name: "synthetic-fixture-value" for name in {**SECRET_FILES, **CONFIG_FILES}}
        paths = []
        with self.assertRaises(ValueError):
            with secret_environment(values) as environment:
                paths = [Path(path) for path in environment.values()]
                self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in paths))
                raise ValueError("test-only validation failure")
        self.assertTrue(paths)
        self.assertTrue(all(not path.exists() for path in paths))
