"""Test environment-probe safety without contacting a live environment."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import secrets
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("verify_staging.py")


class Response:
    def __init__(self, status=200, body=b'{"status":"ok"}'):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, size):
        return self.body[:size]


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "KOLOVIBE_STAGING_URL": "https://staging.example.test",
            "KOLOVIBE_STAGING_HOST": "staging.example.test",
            "KOLOVIBE_STAGING_CHECK_PATH": "/health/protected",
            "KOLOVIBE_STAGING_CHECK_TOKEN": secrets.token_urlsafe(48),
        }

    def execute(self, environment=None, responder=None):
        seen = []

        def response(request, timeout):
            seen.append(request)
            if responder:
                return responder(request)
            return Response() if len(seen) == 1 else Response(403)

        output = io.StringIO()
        with patch.dict(os.environ, environment or self.environment, clear=True):
            with patch("urllib.request.build_opener") as opener:
                opener.return_value.open.side_effect = response
                with redirect_stdout(output):
                    runpy.run_path(str(SCRIPT))
        return seen, output.getvalue()

    def test_only_same_origin_probe_receives_credential(self):
        seen, output = self.execute()
        self.assertEqual(len(seen), 4)
        self.assertEqual(seen[0].full_url, "https://staging.example.test/health/protected")
        self.assertEqual(seen[0].get_header("Authorization"),
                         "Bearer " + self.environment["KOLOVIBE_STAGING_CHECK_TOKEN"])
        self.assertTrue(all(request.get_header("Authorization") is None for request in seen[1:]))
        self.assertNotIn(self.environment["KOLOVIBE_STAGING_CHECK_TOKEN"], output)
        self.assertIn('"authenticated_probe": "passed"', output)

    def test_missing_credentials_and_unapproved_origins_fail(self):
        for key, value in (
            ("KOLOVIBE_STAGING_CHECK_TOKEN", ""),
            ("KOLOVIBE_STAGING_URL", "http://staging.example.test"),
            ("KOLOVIBE_STAGING_URL", "https://other.example.test"),
            ("KOLOVIBE_STAGING_CHECK_PATH", "//other.example.test/probe"),
            ("KOLOVIBE_STAGING_CHECK_PATH", "/../admin"),
            ("KOLOVIBE_STAGING_CHECK_PATH", "/%2e%2e/admin"),
        ):
            environment = dict(self.environment, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(SystemExit):
                self.execute(environment)

    def test_redirect_failure_and_invalid_health_do_not_pass(self):
        for response in (Response(302), Response(401), Response(503),
                         Response(200, b"not-json"),
                         Response(200, json.dumps({"ready": True}).encode())):
            with self.assertRaises(SystemExit):
                self.execute(responder=lambda request: response)

    def test_anonymous_reserved_route_must_not_succeed(self):
        with self.assertRaises(SystemExit):
            self.execute(responder=lambda request: Response())


if __name__ == "__main__":
    unittest.main()
