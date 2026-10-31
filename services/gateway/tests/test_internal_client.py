from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import hmac
import json
import os
import secrets
from django.test import SimpleTestCase
from service.internal_client import signed_internal_request

class SignedClientTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.secret = secrets.token_urlsafe(48)
        (self.root/"key").write_text(self.secret)
        (self.root/"peers").write_text(json.dumps({"identity":"https://identity.internal"}))
        self.config = {
            "KOLOVIBE_SERVICE_NAME": "gateway",
            "KOLOVIBE_TRUSTED_PEERS_FILE": str(self.root/"peers"),
            "KOLOVIBE_OUTBOUND_KEY_FILE": str(self.root/"key"),
        }

    def test_signed_headers_bind_caller_audience_path_and_body(self):
        with patch.dict(os.environ, self.config):
            with patch("service.internal_client.build_opener") as factory:
                factory.return_value.open.return_value = object()
                signed_internal_request("identity", "/internal/probe")
                request = factory.return_value.open.call_args.args[0]
                headers = request.headers
                payload_hash = hashlib.sha256(b"").hexdigest()
                canonical = "\n".join((
                    headers["X-kolovibe-caller"],
                    "identity",
                    headers["X-kolovibe-timestamp"],
                    headers["X-kolovibe-nonce"],
                    "GET",
                    "/internal/probe",
                    payload_hash,
                ))
                expected = hmac.new(self.secret.encode(),canonical.encode(),hashlib.sha256).hexdigest()
                self.assertEqual(headers["X-kolovibe-signature"],expected)
                self.assertEqual(request.full_url,"https://identity.internal/internal/probe")

    def test_rejects_unapproved_audience_and_path(self):
        with patch.dict(os.environ, self.config):
            for audience,path in (("points","/internal/probe"),("identity","/health/live"),("identity","/internal/probe?x=1")):
                with self.subTest(audience=audience,path=path):
                    with self.assertRaises(ValueError):
                        signed_internal_request(audience,path)

    def test_rejects_plaintext_peer(self):
        (self.root/"peers").write_text(json.dumps({"identity":"http://identity.internal"}))
        with patch.dict(os.environ,self.config):
            with self.assertRaises(ValueError):
                signed_internal_request("identity","/internal/probe")
