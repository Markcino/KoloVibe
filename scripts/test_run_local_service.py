"""Tests for local secret loading without storing credential fixtures."""

import tempfile
import unittest
import secrets
from pathlib import Path
from unittest.mock import patch

from init_local_env import create_local_env
from run_local_service import environment_for, read_local_env


class LocalEnvironmentTests(unittest.TestCase):
    def test_app_compatibility_configuration_is_forwarded_only_to_gateway(self):
        values = {f"KOLOVIBE_{service.upper()}_DJANGO_SECRET_KEY": secrets.token_urlsafe(48)
                  for service in ("gateway", "identity")}
        config = {f"KOLOVIBE_APP_{field}_{platform}": value
                  for platform in ("IOS", "ANDROID")
                  for field, value in (("MIN_VERSION", "1.0.0"), ("LATEST_VERSION", "1.1.0"),
                                       ("STORE_URL", "https://store.example.test/app"))}
        values.update(config)
        gateway = environment_for("gateway", values)
        identity = environment_for("identity", values)
        self.assertEqual({key: gateway[key] for key in config}, config)
        self.assertFalse(set(config) & set(identity))

    def test_database_configuration_is_scoped_and_complete(self):
        values = {"KOLOVIBE_IDENTITY_DJANGO_SECRET_KEY": secrets.token_urlsafe(48)}
        values["KOLOVIBE_IDENTITY_DB_PORT"] = "5432"
        with self.assertRaisesRegex(ValueError, "Incomplete PostgreSQL"):
            environment_for("identity", values)
        for key, value in {
            "DB_NAME": "local_test", "DB_USER": "identity_test",
            "DB_HOST": "127.0.0.1", "DB_PASSWORD_FILE": "/test/private",
            "DB_SSLROOTCERT": "/test/ca.crt",
        }.items():
            values["KOLOVIBE_IDENTITY_" + key] = value
        with patch.dict("os.environ", {"KOLOVIBE_DB_USER": "wrong-service",
                                      "KOLOVIBE_RABBITMQ_URL": "must-not-inherit"}):
            environment = environment_for("identity", values)
        self.assertEqual(environment["KOLOVIBE_DB_USER"], "identity_test")
        self.assertNotIn("KOLOVIBE_RABBITMQ_URL", environment)

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

    def test_r2_credentials_and_broker_stay_scoped_to_content(self):
        values = {
            f"KOLOVIBE_{service.upper()}_DJANGO_SECRET_KEY": secrets.token_urlsafe(48)
            for service in ("gateway", "content", "identity")
        }
        values.update({
            "KOLOVIBE_LOCAL_MEDIA_ENABLED": "1",
            "KOLOVIBE_R2_ACCOUNT_ID": "a" * 32,
            "KOLOVIBE_R2_SECRET_KEY_FILE": "/fixture/r2-secret",
            "KOLOVIBE_CONTENT_RABBITMQ_URL": "fixture-broker",
        })
        gateway = environment_for("gateway", values)
        content = environment_for("content", values)
        self.assertEqual(gateway["KOLOVIBE_LOCAL_MEDIA_ENABLED"], "1")
        self.assertEqual(content["KOLOVIBE_R2_SECRET_KEY_FILE"], "/fixture/r2-secret")
        self.assertEqual(content["KOLOVIBE_RABBITMQ_URL"], "fixture-broker")
        self.assertNotIn("KOLOVIBE_R2_SECRET_KEY_FILE", gateway)
        self.assertNotIn("KOLOVIBE_RABBITMQ_URL", gateway)
        self.assertNotIn("KOLOVIBE_LOCAL_MEDIA_ENABLED", environment_for("identity", values))

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
            self.assertEqual(len(values), 17)
            gateway = environment_for("gateway", values)
            engagement = environment_for("engagement", values)
            self.assertEqual(gateway["KOLOVIBE_ENGAGEMENT_URL"], "http://127.0.0.1:8004")
            self.assertEqual(engagement["KOLOVIBE_CALLER_GATEWAY_KEY"],
                             gateway["KOLOVIBE_GATEWAY_OUTBOUND_KEY"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                create_local_env(path)


if __name__ == "__main__":
    unittest.main()
