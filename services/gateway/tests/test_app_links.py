"""Owner decision SIM-02: share links open the app, fall back to a store, and never serve a website."""

import importlib.util
import os
import secrets
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from service import settings as gateway_settings
from service.app_links import load_configuration, share_url
from service.compatibility import validate_configuration

FINGERPRINT = ":".join(["AB"] * 32)
BOTH = {"origin": "https://links.example.test", "ios_app_id": "ABCDE12345.com.kolovibe.kolovibe",
        "android_package": "com.kolovibe.kolovibe", "android_fingerprints": [FINGERPRINT]}
STORES = {"ios": validate_configuration(None, None, "https://apps.apple.com/app/id123"),
          "android": validate_configuration(None, None, "https://play.google.com/store/apps/details?id=com.kolovibe.kolovibe")}
NO_STORES = {"ios": validate_configuration(None, None, None), "android": validate_configuration(None, None, None)}
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
ANDROID = "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"
DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"


@override_settings(APP_LINKS=BOTH, APP_COMPATIBILITY=STORES)
class AppLinkRouteTests(SimpleTestCase):
    def test_share_url_is_the_app_link_path_on_the_configured_origin(self):
        video = uuid4()
        self.assertEqual(share_url(video), f"https://links.example.test/open/videos/{video}")
        for config in ({**BOTH, "origin": None}, {**BOTH, "ios_app_id": None, "android_package": None}):
            with self.subTest(config=config), override_settings(APP_LINKS=config):
                self.assertIsNone(share_url(video))

    def test_association_files_claim_only_the_share_path_for_the_configured_apps(self):
        apple = self.client.get("/.well-known/apple-app-site-association")
        self.assertEqual(apple.status_code, 200)
        self.assertEqual(apple["Content-Type"], "application/json")
        self.assertEqual(apple.json(), {"applinks": {"details": [{
            "appIDs": ["ABCDE12345.com.kolovibe.kolovibe"],
            "components": [{"/": "/open/videos/*", "comment": "Shared KoloVibe videos"}]}]}})
        android = self.client.get("/.well-known/assetlinks.json")
        self.assertEqual(android.status_code, 200)
        self.assertEqual(android.json(), [{
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {"namespace": "android_app", "package_name": "com.kolovibe.kolovibe",
                       "sha256_cert_fingerprints": [FINGERPRINT]}}])
        self.assertEqual(self.client.post("/.well-known/assetlinks.json").status_code, 405)

    def test_unconfigured_platforms_publish_no_association(self):
        with override_settings(APP_LINKS={**BOTH, "ios_app_id": None}):
            self.assertEqual(self.client.get("/.well-known/apple-app-site-association").status_code, 404)
            self.assertEqual(self.client.get("/.well-known/assetlinks.json").status_code, 200)
        with override_settings(APP_LINKS={**BOTH, "origin": None, "ios_app_id": None, "android_package": None,
                                          "android_fingerprints": []}):
            self.assertEqual(self.client.get("/.well-known/apple-app-site-association").status_code, 404)
            self.assertEqual(self.client.get("/.well-known/assetlinks.json").status_code, 404)

    def test_phones_without_the_app_are_sent_to_their_store_and_nothing_else_gets_a_page(self):
        path = reverse("app-link-video", args=[uuid4()])
        with patch("service.videos.signed_internal_request") as content, \
                patch("service.accounts.signed_internal_request") as identity:
            ios = self.client.get(path, HTTP_USER_AGENT=IPHONE)
            self.assertEqual((ios.status_code, ios["Location"]), (302, "https://apps.apple.com/app/id123"))
            android = self.client.get(path, HTTP_USER_AGENT=ANDROID)
            self.assertEqual(android.status_code, 302)
            self.assertTrue(android["Location"].startswith("https://play.google.com/"))
            for agent in (DESKTOP, ""):
                other = self.client.get(path, HTTP_USER_AGENT=agent)
                self.assertEqual(other.status_code, 200)
                self.assertTrue(other["Content-Type"].startswith("text/plain"))
                self.assertNotIn(b"<", other.content)
            with override_settings(APP_COMPATIBILITY=NO_STORES):
                self.assertEqual(self.client.get(path, HTTP_USER_AGENT=IPHONE).status_code, 200)
            # The redirect never looks the video up, so it cannot reveal whether a private video exists.
            content.assert_not_called()
            identity.assert_not_called()
        for response in (ios, other):
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(response["Referrer-Policy"], "no-referrer")
            self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(self.client.get("/open/videos/not-a-uuid", HTTP_USER_AGENT=IPHONE).status_code, 404)
        self.assertEqual(self.client.post(path).status_code, 405)


class AppLinkConfigurationTests(SimpleTestCase):
    def test_empty_configuration_disables_app_links(self):
        self.assertEqual(load_configuration({}), {"origin": None, "ios_app_id": None, "android_package": None,
                                                 "android_fingerprints": []})

    def test_valid_configuration_is_normalized(self):
        config = load_configuration({
            "KOLOVIBE_APP_LINK_ORIGIN": "https://links.example.test/",
            "KOLOVIBE_APP_LINK_IOS_APP_ID": "ABCDE12345.com.kolovibe.kolovibe",
            "KOLOVIBE_APP_LINK_ANDROID_PACKAGE": "com.kolovibe.kolovibe",
            "KOLOVIBE_APP_LINK_ANDROID_SHA256": f"{FINGERPRINT}, {':'.join(['CD'] * 32)}"})
        self.assertEqual(config["origin"], "https://links.example.test")
        self.assertEqual(config["android_fingerprints"], [FINGERPRINT, ":".join(["CD"] * 32)])

    def test_unsafe_or_inconsistent_configuration_stops_start_up(self):
        origin = {"KOLOVIBE_APP_LINK_ORIGIN": "https://links.example.test"}
        userinfo = "user:" + secrets.token_urlsafe(12)
        cases = [{"KOLOVIBE_APP_LINK_ORIGIN": value} for value in (
            "http://links.example.test", "//links.example.test", "https://links.example.test/path",
            f"https://{userinfo}@links.example.test", "https://links.example.test?a=1",
            "https://links.example.test/#fragment", "https://links.example.test:99999",
            "https://links.example.test\\evil")]
        cases += [
            {**origin, "KOLOVIBE_APP_LINK_IOS_APP_ID": "com.kolovibe.kolovibe"},
            {**origin, "KOLOVIBE_APP_LINK_IOS_APP_ID": "abcde12345.com.kolovibe"},
            {**origin, "KOLOVIBE_APP_LINK_IOS_APP_ID": "ABCDE12345.com.kolovibe\n"},
            {**origin, "KOLOVIBE_APP_LINK_ANDROID_PACKAGE": "com.kolovibe.kolovibe"},
            {**origin, "KOLOVIBE_APP_LINK_ANDROID_SHA256": FINGERPRINT},
            {**origin, "KOLOVIBE_APP_LINK_ANDROID_PACKAGE": "kolovibe", "KOLOVIBE_APP_LINK_ANDROID_SHA256": FINGERPRINT},
            {**origin, "KOLOVIBE_APP_LINK_ANDROID_PACKAGE": "com.kolovibe.kolovibe",
             "KOLOVIBE_APP_LINK_ANDROID_SHA256": FINGERPRINT.lower()},
            {**origin, "KOLOVIBE_APP_LINK_ANDROID_PACKAGE": "com.kolovibe.kolovibe",
             "KOLOVIBE_APP_LINK_ANDROID_SHA256": f"{FINGERPRINT},{FINGERPRINT}"},
            {"KOLOVIBE_APP_LINK_IOS_APP_ID": "ABCDE12345.com.kolovibe.kolovibe"},
        ]
        for environ in cases:
            with self.subTest(environ=environ), self.assertRaises(RuntimeError):
                load_configuration(environ)

    def test_settings_load_validates_app_link_configuration(self):
        spec = importlib.util.spec_from_file_location("service._app_link_settings_test", Path(gateway_settings.__file__))
        base = {"KOLOVIBE_ENV": "local", "DJANGO_SECRET_KEY": secrets.token_urlsafe(48)}
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {**base, "KOLOVIBE_APP_LINK_ORIGIN": "https://links.example.test/",
                                     "KOLOVIBE_APP_LINK_IOS_APP_ID": "ABCDE12345.com.kolovibe.kolovibe"}, clear=True):
            spec.loader.exec_module(module)
        self.assertEqual(module.APP_LINKS["origin"], "https://links.example.test")
        with patch.dict(os.environ, {**base, "KOLOVIBE_APP_LINK_ORIGIN": "http://links.example.test"}, clear=True), \
                self.assertRaises(RuntimeError):
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
