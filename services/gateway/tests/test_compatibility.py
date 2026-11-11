import importlib.util
import os
import secrets
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from service import settings as gateway_settings
from service.compatibility import validate_configuration, version_key


class AppCompatibilityTests(SimpleTestCase):
    def get(self, platform="ios", version="1.2.3"):
        return self.client.get(reverse("app-compatibility"), {"platform": platform, "version": version})

    def test_public_unconfigured_platforms_return_exact_unknown_shape(self):
        empty = validate_configuration(None, None, None)
        with override_settings(APP_COMPATIBILITY={"ios": empty, "android": empty}), \
                patch("service.accounts.signed_internal_request") as call:
            for platform in ("ios", "android"):
                response = self.get(platform)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": "unknown", "minimum_version": None,
                                                   "latest_version": None, "store_url": None})
                self.assertIn("no-store", response.headers["Cache-Control"])
            call.assert_not_called()

    def test_version_policy_is_numeric_platform_specific_and_inclusive(self):
        ios = validate_configuration("1.2.0", "1.10.0", "https://apps.apple.com/app/id123")
        android = validate_configuration("2.0.0", "2.1.0", "https://play.google.com/store/apps/details?id=test.app")
        with override_settings(APP_COMPATIBILITY={"ios": ios, "android": android}):
            for version, expected in (("1.1.99", "update_required"), ("1.2.0", "update_available"),
                                      ("1.9.0", "update_available"), ("1.10.0", "supported"),
                                      ("2.0.0", "supported")):
                self.assertEqual(self.get(version=version).json(), {"status": expected, **ios})
            self.assertEqual(self.get("android", "1.10.0").json(), {"status": "update_required", **android})

    def test_semver_prerelease_precedence_and_build_metadata(self):
        ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
                   "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
        self.assertEqual(sorted(reversed(ordered), key=version_key), ordered)
        self.assertEqual(version_key("1.2.3+build.001"), version_key("1.2.3+different"))
        config = validate_configuration("1.2.3", "1.2.3", None)
        with override_settings(APP_COMPATIBILITY={"ios": config, "android": config}):
            self.assertEqual(self.get(version="1.2.3-rc.1").json()["status"], "update_required")
            self.assertEqual(self.get(version="1.2.3+build.001").json()["status"], "supported")

    def test_bad_missing_extra_or_duplicate_query_parameters_are_400(self):
        path = reverse("app-compatibility")
        for query in ("", "platform=ios", "version=1.2.3", "platform=web&version=1.2.3",
                      "platform=IOS&version=1.2.3", "platform=ios&version=1.2.3&extra=1",
                      "platform=ios&platform=android&version=1.2.3",
                      "platform=ios&version=1.2.3&version=2.0.0"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(path + "?" + query).status_code, 400)
        for version in ("1", "1.2", "v1.2.3", "01.2.3", "1.02.3", "1.2.03", "-1.2.3",
                        "1.2.3.4", "1.2.3-01", "1.2.3-", "1.2.3+", "1.2.3+a..b",
                        "1.2.3\n", " 1.2.3", "١.2.3", "x" * 129):
            with self.subTest(version=version):
                self.assertEqual(self.get(version=version).status_code, 400)
        self.assertEqual(self.client.post(path).status_code, 405)

    def load_settings(self, extra):
        spec = importlib.util.spec_from_file_location("service._compatibility_settings_test",
                                                     Path(gateway_settings.__file__))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"KOLOVIBE_ENV": "local",
                                    "DJANGO_SECRET_KEY": secrets.token_urlsafe(48), **extra}, clear=True):
            spec.loader.exec_module(module)
        return module

    def test_all_six_environment_settings_are_loaded_at_startup(self):
        config = {}
        for platform in ("IOS", "ANDROID"):
            config.update({f"KOLOVIBE_APP_MIN_VERSION_{platform}": "1.0.0",
                           f"KOLOVIBE_APP_LATEST_VERSION_{platform}": "1.2.0",
                           f"KOLOVIBE_APP_STORE_URL_{platform}": "https://store.example.test/app"})
        loaded = self.load_settings(config)
        for platform in ("ios", "android"):
            self.assertEqual(loaded.APP_COMPATIBILITY[platform], {
                "minimum_version": "1.0.0", "latest_version": "1.2.0",
                "store_url": "https://store.example.test/app"})

    def test_unsafe_store_urls_and_invalid_versions_fail_settings_load(self):
        userinfo = "user:" + secrets.token_urlsafe(12)
        for url in ("http://store.example.test/app", "javascript:alert(1)", "//store.example.test",
                    "https:///app", f"https://{userinfo}@store.example.test/app",
                    "https://store.example.test/\napp", "https://store.example.test\\evil/app"):
            with self.subTest(url=url), self.assertRaisesRegex(RuntimeError, "compatibility configuration"):
                self.load_settings({"KOLOVIBE_APP_STORE_URL_IOS": url})
        for name in ("KOLOVIBE_APP_MIN_VERSION_ANDROID", "KOLOVIBE_APP_LATEST_VERSION_IOS"):
            with self.assertRaises(RuntimeError):
                self.load_settings({name: "01.2.3"})
        with self.assertRaises(RuntimeError):
            self.load_settings({"KOLOVIBE_APP_MIN_VERSION_IOS": "2.0.0",
                                "KOLOVIBE_APP_LATEST_VERSION_IOS": "1.0.0"})

    def test_partial_configuration_uses_only_known_bounds(self):
        lower = validate_configuration("1.0.0", None, None)
        upper = validate_configuration(None, "2.0.0", None)
        with override_settings(APP_COMPATIBILITY={"ios": lower, "android": upper}):
            self.assertEqual(self.get().json(), {"status": "supported", **lower})
            self.assertEqual(self.get("android").json(), {"status": "update_available", **upper})
