"""Fail-closed staging configuration and deployment candidate regression tests."""

import copy
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.validate_staging_stack import ROOT, load_stack, validate

sys.path.insert(0, str(ROOT / "services"))
from staging_runtime import configure, json_file, secret


class StagingConfigurationTests(unittest.TestCase):
    def test_secrets_require_owner_only_nonempty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            path.touch(mode=0o600)
            path.write_text(secrets.token_urlsafe(48))
            with patch.dict(os.environ, {"TEST_KEY_FILE": str(path)}, clear=True):
                self.assertGreaterEqual(len(secret("TEST_KEY_FILE")), 32)
                path.chmod(0o644)
                with self.assertRaisesRegex(RuntimeError, "owner-only"):
                    secret("TEST_KEY_FILE")
                path.chmod(0o600)
                path.write_text("")
                with self.assertRaisesRegex(RuntimeError, "Empty"):
                    secret("TEST_KEY_FILE")

    def test_missing_secret_does_not_fall_back_to_environment_value(self):
        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": secrets.token_urlsafe(48)}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Missing"):
                secret("DJANGO_SECRET_KEY_FILE")

    def test_json_object_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config"
            for value in ("broken", "[]", '"not-an-object"'):
                path.write_text(value)
                with patch.dict(os.environ, {"CONFIG": str(path)}, clear=True):
                    with self.assertRaises(RuntimeError):
                        json_file("CONFIG")

    def test_wrong_service_debug_hosts_and_sqlite_are_rejected(self):
        settings = {"KOLOVIBE_SERVICE_NAME": "content",
                    "DATABASES": {"default": {"ENGINE": "django.db.backends.sqlite3"}}}
        environment = {"KOLOVIBE_SERVICE_NAME": "content", "KOLOVIBE_ALLOWED_HOSTS": "content"}
        for changes in ({"KOLOVIBE_SERVICE_NAME": "identity"}, {"DJANGO_DEBUG": "1"},
                        {"KOLOVIBE_ALLOWED_HOSTS": "*"}, {"KOLOVIBE_ALLOWED_HOSTS": "testserver"},
                        {"KOLOVIBE_ALLOWED_HOSTS": "content:8000"}, {}):
            with patch.dict(os.environ, dict(environment, **changes), clear=True):
                with self.assertRaises(RuntimeError):
                    configure(copy.deepcopy(settings))

    def test_mutating_caller_keys_after_startup_is_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "callers"
            path.touch(mode=0o600)
            with patch.dict(os.environ, {"CALLERS": str(path)}, clear=True):
                old, new = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
                path.write_text(json.dumps({"gateway": old}))
                self.assertEqual(json_file("CALLERS", private=True)["gateway"], old)
                path.write_text(json.dumps({"gateway": new}))
                self.assertEqual(json_file("CALLERS", private=True)["gateway"], new)


class StagingManifestTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "STAGING_DB_NAME": "fixture", "STAGING_DB_HOST": "db.example.test",
            "STAGING_PRIVATE_NETWORK": "fixture-private", "GATEWAY_HOSTS": "gateway",
            **{name.upper() + "_DB_USER": "runtime_" + name
               for name in ("gateway", "content", "creators")},
            **{name.upper() + "_IMAGE": f"ghcr.io/markcino/kolovibe/{name}@sha256:" + "a" * 64
               for name in ("gateway", "content", "creators")},
        }
        self.stack = load_stack(ROOT / "infra/swarm/staging.yml", self.environment)

    def test_reviewed_candidate_shape(self):
        validate(self.stack)

    def test_missing_environment_inputs_cannot_render(self):
        with self.assertRaises(ValueError):
            load_stack(ROOT / "infra/swarm/staging.yml", {})

    def test_mutable_images_credentials_ports_and_account_flags_cannot_pass(self):
        for changes in (
            {"image": "ghcr.io/markcino/kolovibe/gateway:latest"},
            {"ports": ["8000:8000"]}, {"user": "root"}, {"read_only": False},
            {"volumes": ["/:/host"]},
        ):
            stack = copy.deepcopy(self.stack)
            stack["services"]["gateway"].update(changes)
            with self.assertRaises(ValueError):
                validate(stack)
        for changes in ({"KOLOVIBE_ENV": "local"}, {"KOLOVIBE_STAGING_ACCOUNTS": "1"},
                        {"KOLOVIBE_DB_PASSWORD": "not-allowed"}):
            stack = copy.deepcopy(self.stack)
            stack["services"]["gateway"]["environment"].update(changes)
            with self.assertRaises(ValueError):
                validate(stack)

    def test_nginx_does_not_expose_internal_or_accounts_and_verifies_tls(self):
        config = (ROOT / "infra/nginx/staging.conf.template").read_text()
        self.assertIn("proxy_ssl_verify on;", config)
        self.assertIn('proxy_set_header X-Forwarded-Proto "";', config)
        self.assertIn("location / { return 403; }", config)
        self.assertNotIn("/auth", config)
        self.assertNotIn("proxy_ssl_verify off", config)

    def test_image_has_wsgi_runtime_and_only_shared_infrastructure(self):
        config = (ROOT / "infra/docker/Dockerfile.service").read_text()
        self.assertIn('"staging_runtime.wsgi:application"', config)
        self.assertIn("services/staging_runtime/", config)
        self.assertNotIn("runserver", config)


if __name__ == "__main__":
    unittest.main()
