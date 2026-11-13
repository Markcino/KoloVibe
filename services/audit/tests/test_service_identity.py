"""Per-peer service identity: impersonation, signature, replay and credential negative tests.

This file is identical in every service (scripts/test_service_identity_drift.py enforces it) and
derives its expectations from the service's own CALLER_PATHS policy.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.db import connection
from django.test import RequestFactory, TestCase

from service.service_auth import CALLER_PATHS, ServiceAuthMiddleware

SERVICE = Path(__file__).resolve().parents[1].name
EVERY_SERVICE = ("gateway", "identity", "creators", "content", "engagement", "points", "moderation", "audit")
ALLOWED = sorted(CALLER_PATHS)
FORBIDDEN_BODY = b'{"detail": "Forbidden"}'


def permitted_path(caller):
    rule = CALLER_PATHS[caller][0]
    return rule + "probe" if rule.endswith("/") else rule


class ServiceIdentityTests(TestCase):
    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS internal_request_nonce (caller text NOT NULL, "
                "nonce text NOT NULL, received_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "PRIMARY KEY (caller, nonce))")
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.keyfile = Path(self.temp.name) / "callers.json"
        # A key for every service, so tests can prove that a valid-looking key alone is not enough.
        self.keys = {name: secrets.token_urlsafe(48) for name in EVERY_SERVICE}
        self.write_keys(self.keys)
        self.middleware = ServiceAuthMiddleware(lambda request: _Ok(getattr(request, "service_caller", None)))
        self.environment = {
            "KOLOVIBE_ENV": "contract-test", "KOLOVIBE_SERVICE_NAME": SERVICE,
            "KOLOVIBE_CALLER_KEYS_FILE": str(self.keyfile),
        }
        for name in ("KOLOVIBE_CALLER_GATEWAY_KEY", "KOLOVIBE_CALLER_MODERATION_KEY"):
            self.environment[name] = ""

    def write_keys(self, value):
        self.keyfile.write_text(value if isinstance(value, str) else json.dumps(value))

    def signed(self, caller, key, *, path=None, audience=None, body=b"{}", method="POST",
               stamp=None, nonce=None, sign_method=None, sign_path=None, sign_body=None):
        path = path or (permitted_path(caller) if caller in CALLER_PATHS else "/internal/probe")
        stamp = str(int(time.time())) if stamp is None else str(stamp)
        nonce = nonce or secrets.token_urlsafe(24)
        canonical = "\n".join((caller, audience or SERVICE, stamp, nonce, sign_method or method,
                               sign_path or path, hashlib.sha256(body if sign_body is None else sign_body).hexdigest()))
        signature = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        return RequestFactory().generic(
            method, path, data=body, content_type="application/json",
            HTTP_X_KOLOVIBE_CALLER=caller, HTTP_X_KOLOVIBE_TIMESTAMP=stamp,
            HTTP_X_KOLOVIBE_NONCE=nonce, HTTP_X_KOLOVIBE_SIGNATURE=signature)

    def call(self, request, **environment):
        with patch.dict(os.environ, {**self.environment, **environment}):
            response = self.middleware(request)
        if getattr(response, "status_code", None) == 403:
            self.assertEqual(response.content, FORBIDDEN_BODY)
        return response

    def assert_denied(self, request, **environment):
        self.assertEqual(self.call(request, **environment).status_code, 403)

    def first_caller(self):
        if not ALLOWED:
            self.skipTest("This service accepts no internal callers")
        return ALLOWED[0]

    # --- identity policy -------------------------------------------------------------------

    def test_each_allowed_caller_is_accepted_with_only_its_own_key(self):
        for caller in ALLOWED:
            with self.subTest(caller=caller):
                response = self.call(self.signed(caller, self.keys[caller]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.caller, caller)

    def test_service_without_internal_callers_denies_every_service(self):
        if ALLOWED:
            self.skipTest("This service accepts internal callers")
        for caller in EVERY_SERVICE:
            with self.subTest(caller=caller):
                self.assert_denied(self.signed(caller, self.keys[caller], path="/internal/probe"))

    def test_unlisted_service_is_denied_even_with_a_valid_signature_and_key(self):
        for caller in set(EVERY_SERVICE) - set(ALLOWED):
            with self.subTest(caller=caller):
                self.assert_denied(self.signed(caller, self.keys[caller], path="/internal/probe"))

    def test_cross_peer_impersonation_with_another_services_key_is_denied(self):
        caller = self.first_caller()
        for other in set(EVERY_SERVICE) - {caller}:
            with self.subTest(signing_key_of=other):
                self.assert_denied(self.signed(caller, self.keys[other]))
        # A key that belongs to a different receiver, and so is absent from this file, is useless here.
        self.assert_denied(self.signed(caller, secrets.token_urlsafe(48)))

    def test_signature_made_for_another_audience_is_denied(self):
        caller = self.first_caller()
        for audience in set(EVERY_SERVICE) - {SERVICE}:
            with self.subTest(audience=audience):
                self.assert_denied(self.signed(caller, self.keys[caller], audience=audience))

    def test_caller_outside_its_path_policy_is_denied(self):
        for caller in ALLOWED:
            if "/internal/" in CALLER_PATHS[caller]:
                continue
            with self.subTest(caller=caller):
                self.assert_denied(self.signed(caller, self.keys[caller], path="/internal/not-permitted"))

    def test_non_internal_paths_are_not_handled_by_service_auth(self):
        self.assertEqual(self.call(RequestFactory().get("/health/live")).status_code, 200)

    # --- signature, timestamp and nonce validity --------------------------------------------

    def test_tampered_request_is_denied(self):
        caller = self.first_caller()
        key = self.keys[caller]
        cases = {
            "body": self.signed(caller, key, body=b'{"x": 1}', sign_body=b"{}"),
            "method": self.signed(caller, key, method="PUT", sign_method="POST"),
            "path": self.signed(caller, key, path=permitted_path(caller), sign_path="/internal/other"),
        }
        for name, request in cases.items():
            with self.subTest(tampered=name):
                self.assert_denied(request)

    def test_malformed_signatures_are_denied(self):
        caller = self.first_caller()
        for signature in ("0" * 64, "g" * 64, "a" * 63, "A" * 64, ""):
            with self.subTest(signature=signature):
                request = self.signed(caller, self.keys[caller])
                request.META["HTTP_X_KOLOVIBE_SIGNATURE"] = signature
                self.assert_denied(request)

    def test_stale_and_future_timestamps_are_denied(self):
        caller = self.first_caller()
        for offset in (-120, 120):
            with self.subTest(offset=offset):
                self.assert_denied(self.signed(caller, self.keys[caller], stamp=int(time.time()) + offset))

    def test_malformed_identity_headers_are_denied(self):
        caller = self.first_caller()
        for name, value in (("HTTP_X_KOLOVIBE_NONCE", "short"), ("HTTP_X_KOLOVIBE_TIMESTAMP", "12"),
                            ("HTTP_X_KOLOVIBE_CALLER", "Gateway"), ("HTTP_X_KOLOVIBE_CALLER", "")):
            with self.subTest(header=name, value=value):
                request = self.signed(caller, self.keys[caller])
                request.META[name] = value
                self.assert_denied(request)

    def test_replayed_request_is_denied(self):
        caller = self.first_caller()
        request = self.signed(caller, self.keys[caller])
        self.assertEqual(self.call(request).status_code, 200)
        self.assert_denied(request)

    def test_nonce_is_not_consumed_by_a_forged_request(self):
        caller = self.first_caller()
        nonce = secrets.token_urlsafe(24)
        self.assert_denied(self.signed(caller, secrets.token_urlsafe(48), nonce=nonce))
        self.assertEqual(self.call(self.signed(caller, self.keys[caller], nonce=nonce)).status_code, 200)

    # --- missing or unsafe credentials ------------------------------------------------------

    def test_missing_or_unusable_credentials_fail_closed(self):
        caller = self.first_caller()
        request = lambda: self.signed(caller, self.keys[caller])
        self.assert_denied(request(), KOLOVIBE_CALLER_KEYS_FILE="")
        self.assert_denied(request(), KOLOVIBE_CALLER_KEYS_FILE=str(Path(self.temp.name) / "missing"))
        self.assert_denied(request(), KOLOVIBE_SERVICE_NAME="")
        for broken in ("not json", "[]", "null", '"text"'):
            with self.subTest(contents=broken):
                self.write_keys(broken)
                self.assert_denied(request())

    def test_caller_without_a_configured_key_or_with_a_weak_key_is_denied(self):
        caller = self.first_caller()
        self.write_keys({name: key for name, key in self.keys.items() if name != caller})
        self.assert_denied(self.signed(caller, self.keys[caller]))
        for weak in ("short", "", None, 12345678901234567890123456789012345):
            with self.subTest(weak=weak):
                self.write_keys({**self.keys, caller: weak})
                self.assert_denied(self.signed(caller, str(weak).ljust(40, "x")))

    def test_one_credential_shared_by_two_callers_is_refused(self):
        caller = self.first_caller()
        self.write_keys({**self.keys, "decoy": self.keys[caller]})
        self.assert_denied(self.signed(caller, self.keys[caller]))
        self.write_keys({**self.keys, "decoy": [self.keys[caller]]})
        self.assert_denied(self.signed(caller, self.keys[caller]))

    def test_rotation_overlap_accepts_two_keys_then_only_the_new_one(self):
        caller = self.first_caller()
        old, new = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        self.write_keys({**self.keys, caller: [new, old]})
        self.assertEqual(self.call(self.signed(caller, new)).status_code, 200)
        self.assertEqual(self.call(self.signed(caller, old)).status_code, 200)
        self.assert_denied(self.signed(caller, self.keys[caller]))
        self.write_keys({**self.keys, caller: [new]})
        self.assert_denied(self.signed(caller, old))
        self.assertEqual(self.call(self.signed(caller, new)).status_code, 200)

    def test_more_than_two_keys_or_an_empty_list_is_refused(self):
        caller = self.first_caller()
        keys = [secrets.token_urlsafe(48) for _ in range(3)]
        for value in (keys, []):
            with self.subTest(count=len(value)):
                self.write_keys({**self.keys, caller: value})
                self.assert_denied(self.signed(caller, keys[0] if keys else self.keys[caller]))

    def test_local_keys_are_ignored_outside_local_environment(self):
        caller = self.first_caller()
        stray = secrets.token_urlsafe(48)
        self.write_keys({name: key for name, key in self.keys.items() if name != caller})
        self.assert_denied(self.signed(caller, stray), KOLOVIBE_CALLER_GATEWAY_KEY=stray,
                           KOLOVIBE_CALLER_MODERATION_KEY=stray)


class _Ok:
    status_code = 200

    def __init__(self, caller=None):
        self.caller = caller

