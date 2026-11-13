"""Per-audience signing credentials on the outbound client (identical in every service)."""
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from service.internal_client import signed_internal_request

SERVICE = Path(__file__).resolve().parents[1].name
PEERS = {"content": "https://content.internal", "creators": "https://creators.internal",
         "audit": "https://audit.internal"}
PATH = "/internal/probe"


class OutboundSigningKeyTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.keys = {name: secrets.token_urlsafe(48) for name in PEERS}
        self.environment = {
            "KOLOVIBE_ENV": "contract-test", "KOLOVIBE_SERVICE_NAME": SERVICE,
            "KOLOVIBE_TRUSTED_PEERS_FILE": str(self.root / "peers"),
            "KOLOVIBE_OUTBOUND_KEY_FILE": str(self.root / "outbound"),
        }
        (self.root / "peers").write_text(json.dumps(PEERS))
        self.write_outbound(self.keys)

    def write_outbound(self, value):
        (self.root / "outbound").write_text(value if isinstance(value, str) else json.dumps(value))

    def sign(self, audience, **environment):
        """Return the request headers the real client would send."""
        with patch.dict(os.environ, {**self.environment, **environment}):
            with patch("service.internal_client.build_opener") as factory:
                factory.return_value.open.return_value = object()
                signed_internal_request(audience, PATH)
                return factory.return_value.open.call_args.args[0].headers

    def valid_for(self, headers, audience, key):
        canonical = "\n".join((headers["X-kolovibe-caller"], audience, headers["X-kolovibe-timestamp"],
                               headers["X-kolovibe-nonce"], "GET", PATH, hashlib.sha256(b"").hexdigest()))
        expected = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(headers["X-kolovibe-signature"], expected)

    def test_each_audience_is_signed_with_its_own_credential_only(self):
        for audience in PEERS:
            headers = self.sign(audience)
            for owner, key in self.keys.items():
                with self.subTest(audience=audience, key_of=owner):
                    self.assertEqual(self.valid_for(headers, audience, key), owner == audience)

    def test_signature_for_one_audience_does_not_verify_for_another(self):
        headers = self.sign("content")
        for other in set(PEERS) - {"content"}:
            self.assertFalse(self.valid_for(headers, other, self.keys["content"]))
            self.assertFalse(self.valid_for(headers, other, self.keys[other]))

    def test_audience_without_a_credential_fails_closed(self):
        self.write_outbound({name: key for name, key in self.keys.items() if name != "creators"})
        with self.assertRaises(RuntimeError):
            self.sign("creators")
        self.assertTrue(self.valid_for(self.sign("content"), "content", self.keys["content"]))

    def test_one_credential_reused_for_two_audiences_is_refused(self):
        self.write_outbound({**self.keys, "creators": self.keys["content"]})
        for audience in ("content", "creators"):
            with self.subTest(audience=audience), self.assertRaises(RuntimeError):
                self.sign(audience)

    def test_weak_or_malformed_credentials_are_refused(self):
        for broken in ({"content": "short"}, {"content": 12345}, {}, "{not json", '{"content": ["a"]}'):
            with self.subTest(contents=broken):
                self.write_outbound(broken)
                with self.assertRaises((RuntimeError, ValueError)):
                    self.sign("content")

    def test_single_legacy_credential_serves_only_a_single_peer(self):
        key = secrets.token_urlsafe(48)
        self.write_outbound(key)
        with self.assertRaises(RuntimeError):  # three peers would share one key
            self.sign("content")
        (self.root / "peers").write_text(json.dumps({"audit": PEERS["audit"]}))
        self.assertTrue(self.valid_for(self.sign("audit"), "audit", key))
        self.write_outbound("short")
        with self.assertRaises(RuntimeError):
            self.sign("audit")

    def test_missing_credential_file_or_configuration_fails_closed(self):
        with self.assertRaises(OSError):
            self.sign("content", KOLOVIBE_OUTBOUND_KEY_FILE=str(self.root / "absent"))
        with patch.dict(os.environ, self.environment):
            os.environ.pop("KOLOVIBE_OUTBOUND_KEY_FILE")
            with self.assertRaises(KeyError):
                signed_internal_request("content", PATH)

    def test_local_environment_keys_are_not_used_outside_local(self):
        self.environment.pop("KOLOVIBE_OUTBOUND_KEY_FILE")
        stray = secrets.token_urlsafe(48)
        with self.assertRaises(KeyError):
            self.sign("content", KOLOVIBE_GATEWAY_OUTBOUND_KEY=stray, KOLOVIBE_MODERATION_OUTBOUND_KEY=stray,
                      KOLOVIBE_GATEWAY_OUTBOUND_KEY_CONTENT=stray, KOLOVIBE_MODERATION_OUTBOUND_KEY_CONTENT=stray)
