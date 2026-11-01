"""Tests for local secret loading without storing credential fixtures."""

import tempfile
import unittest
import secrets
from pathlib import Path

from init_local_env import create_local_env
from run_local_service import environment_for, read_local_env


class LocalEnvironmentTests(unittest.TestCase):
    def test_rejects_world_readable_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("KOLOVIBE_ENV=local\n")
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "permissions"):
                read_local_env(path)

    def test_service_receives_only_its_own_secret(self):
        identity_secret = secrets.token_urlsafe(48)
        points_secret = secrets.token_urlsafe(48)
        values = {
            "KOLOVIBE_ENV": "local",
            "KOLOVIBE_IDENTITY_DJANGO_SECRET_KEY": identity_secret,
            "KOLOVIBE_POINTS_DJANGO_SECRET_KEY": points_secret,
        }
        env = environment_for("identity", values)
        self.assertEqual(env["DJANGO_SECRET_KEY"], identity_secret)
        self.assertNotIn("KOLOVIBE_POINTS_DJANGO_SECRET_KEY", env)

    def test_rejects_missing_service_secret(self):
        with self.assertRaisesRegex(ValueError, "KOLOVIBE_IDENTITY"):
            environment_for("identity", {"KOLOVIBE_ENV": "local"})

    def test_rejects_duplicate_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("KOLOVIBE_ENV=local\nKOLOVIBE_ENV=local\n")
            path.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "repeated"):
                read_local_env(path)

    def test_initialization_is_private_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            create_local_env(path)
            values = read_local_env(path)
            self.assertEqual(len(values), 16)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                create_local_env(path)


if __name__ == "__main__":
    unittest.main()
