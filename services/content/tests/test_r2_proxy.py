"""R2 access through the restricted CONNECT proxy: tunnelling, fail-closed configuration and TLS verification.

A throwaway proxy and TLS origin run on loopback; nothing here reaches the network or a real R2 credential.
"""
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import subprocess
from tempfile import TemporaryDirectory
import threading
from unittest import skipUnless
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from django.test import SimpleTestCase

from service import media_storage

ACCOUNT = "a" * 32
HOST = f"{ACCOUNT}.r2.cloudflarestorage.com"


def make_certificate(directory, name):
    cert, key = Path(directory) / f"{name}.pem", Path(directory) / f"{name}.key"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-keyout", str(key),
                    "-out", str(cert), "-subj", f"/CN={HOST}", "-addext", f"subjectAltName=DNS:{HOST}"],
                   check=True, capture_output=True)
    return str(cert), str(key)


class FakeProxy:
    """Accepts one CONNECT, answers with `status`, and for 200 serves TLS as the origin using `cert`."""

    def __init__(self, cert, key, status=200):
        self.status, self.connect, self.request = status, None, None
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(cert, key)
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        try:
            conn, _ = self.listener.accept()
            conn.settimeout(5)
            data = b""
            while b"\r\n\r\n" not in data:
                data += conn.recv(4096)
            self.connect = data.split(b"\r\n")[0].decode()
            if self.status != 200:
                conn.sendall(f"HTTP/1.1 {self.status} Denied\r\nContent-Length: 0\r\n\r\n".encode())
                return conn.close()
            conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            with self.context.wrap_socket(conn, server_side=True) as tls:
                data = b""
                while b"\r\n\r\n" not in data:
                    data += tls.recv(4096)
                self.request = data.decode()
                tls.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nContent-Type: video/mp4\r\nETag: \"e\"\r\n\r\n")
        except (OSError, ssl.SSLError):
            pass
        finally:
            self.listener.close()

    def close(self):
        self.thread.join(5)


@skipUnless(shutil.which("openssl"), "openssl is needed to build the throwaway certificates")
class R2ProxyTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cert, self.key = make_certificate(self.directory.name, "trusted")
        self.other_cert, self.other_key = make_certificate(self.directory.name, "other")
        for name in ("access", "secret"):
            path = Path(self.directory.name) / name
            path.write_text(secrets.token_hex(32))
            path.chmod(0o400)
        self.env = {"KOLOVIBE_ENV": "staging", "KOLOVIBE_R2_ACCOUNT_ID": ACCOUNT, "KOLOVIBE_R2_MEDIA_BUCKET": "bucket-one",
                    "KOLOVIBE_R2_ACCESS_KEY_FILE": str(Path(self.directory.name) / "access"),
                    "KOLOVIBE_R2_SECRET_KEY_FILE": str(Path(self.directory.name) / "secret")}
        self.key_name = f"originals/{uuid4()}.mp4"
        trust = ssl.create_default_context
        patcher = patch("service.media_storage.ssl.create_default_context",
                        lambda *a, **k: trust(cafile=self.cert))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_head(self, proxy_url, proxy):
        env = dict(self.env, KOLOVIBE_R2_HTTPS_PROXY=proxy_url)
        with patch.dict("os.environ", env):
            try:
                return media_storage.inspect_upload(self.key_name)
            finally:
                proxy and proxy.close()

    def test_connect_tunnel_keeps_signed_host_and_verified_tls(self):
        proxy = FakeProxy(self.cert, self.key)
        self.assertEqual(self.run_head(f"http://127.0.0.1:{proxy.port}", proxy), (5, "video/mp4", '"e"'))
        self.assertRegex(proxy.connect, rf"CONNECT {re.escape(HOST)}:443 HTTP/1\.[01]")
        lines = proxy.request.split("\r\n")
        self.assertTrue(lines[0].startswith(f"HEAD /bucket-one/{self.key_name}?X-Amz-"))
        self.assertIn(f"Host: {HOST}", lines)
        query = parse_qs(urlsplit(lines[0].split()[1]).query)
        self.assertEqual(query["X-Amz-SignedHeaders"], ["host"])

    def test_proxy_rejection_is_storage_unavailable(self):
        for status in (403, 407, 502):
            with self.subTest(status):
                proxy = FakeProxy(self.cert, self.key, status)
                with self.assertRaises(media_storage.StorageUnavailable):
                    self.run_head(f"http://127.0.0.1:{proxy.port}", proxy)

    def test_unreachable_proxy_is_storage_unavailable_with_no_direct_fallback(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        with patch("service.media_storage.HTTPSConnection", wraps=media_storage.HTTPSConnection) as factory:
            with self.assertRaises(media_storage.StorageUnavailable):
                self.run_head(f"http://127.0.0.1:{port}", None)
        self.assertEqual(factory.call_args.args[:2], ("127.0.0.1", port))

    def test_origin_certificate_not_trusted_is_refused(self):
        proxy = FakeProxy(self.other_cert, self.other_key)
        with self.assertRaises(media_storage.StorageUnavailable):
            self.run_head(f"http://127.0.0.1:{proxy.port}", proxy)

    def test_origin_certificate_for_wrong_hostname_is_refused(self):
        proxy = FakeProxy(self.cert, self.key)
        wrong = dict(self.env, KOLOVIBE_R2_ACCOUNT_ID="b" * 32, KOLOVIBE_R2_HTTPS_PROXY=f"http://127.0.0.1:{proxy.port}")
        with patch.dict("os.environ", wrong), self.assertRaises(media_storage.StorageUnavailable):
            media_storage.inspect_upload(self.key_name)
        proxy.close()

    def test_malformed_or_missing_proxy_configuration_fails_closed(self):
        bad = ("https://proxy:3128", "socks5://proxy:3128", "proxy:3128", "http://user:pw@proxy:3128",
               "http://user@proxy:3128", "http://:pw@proxy:3128", "http://proxy", "http://proxy:3128/path",
               "http://proxy:3128/?a=b", "http://proxy:3128?a=b", "http://proxy:3128#x", "http://proxy:99999",
               "http://proxy:abc", "http://[::1", "http://Pro xy:3128", "http:///x", " ", "")
        with patch("service.media_storage.HTTPSConnection") as factory:
            for value in bad:
                for environment in ("staging", "production", None):
                    with self.subTest(value=value, environment=environment):
                        env = {key: val for key, val in dict(self.env, KOLOVIBE_ENV=environment or "",
                                                             KOLOVIBE_R2_HTTPS_PROXY=value).items()}
                        with patch.dict("os.environ", env):
                            with self.assertRaises(media_storage.StorageUnavailable):
                                media_storage.inspect_upload(self.key_name)
        factory.assert_not_called()

    def test_direct_access_is_allowed_only_for_local_development(self):
        with patch.dict("os.environ", {"KOLOVIBE_ENV": "local"}, clear=False):
            with patch.dict("os.environ", {"KOLOVIBE_R2_HTTPS_PROXY": ""}):
                self.assertIsNone(media_storage._proxy_endpoint())
        for environment in ("staging", "contract-test", ""):
            with patch.dict("os.environ", {"KOLOVIBE_ENV": environment, "KOLOVIBE_R2_HTTPS_PROXY": ""}):
                with self.assertRaises(media_storage.StorageUnavailable):
                    media_storage._proxy_endpoint()

    def test_valid_proxy_forms_are_accepted(self):
        for value, expected in (("http://kolovibe-r2-proxy:3128", ("kolovibe-r2-proxy", 3128)),
                                ("http://10.0.5.7:3128/", ("10.0.5.7", 3128))):
            with patch.dict("os.environ", {"KOLOVIBE_ENV": "staging", "KOLOVIBE_R2_HTTPS_PROXY": value}):
                self.assertEqual(media_storage._proxy_endpoint(), expected)

    def test_failures_do_not_leak_presigned_urls_or_credentials(self):
        proxy = FakeProxy(self.cert, self.key, 403)
        with self.assertLogs(level="DEBUG") as logs, self.assertRaises(media_storage.StorageUnavailable) as caught:
            import logging
            logging.getLogger("probe").debug("start")
            self.run_head(f"http://127.0.0.1:{proxy.port}", proxy)
        text = repr(caught.exception) + str(caught.exception.__cause__) + "".join(logs.output)
        self.assertNotIn("X-Amz-Signature", text)
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_upload_and_download_paths_share_the_tunnelled_connection(self):
        for call in ("inspect", "download", "put"):
            with self.subTest(call):
                proxy = FakeProxy(self.cert, self.key)
                path = Path(self.directory.name) / "body"
                path.write_bytes(b"12345")
                env = dict(self.env, KOLOVIBE_R2_HTTPS_PROXY=f"http://127.0.0.1:{proxy.port}")
                with patch.dict("os.environ", env):
                    try:
                        if call == "inspect":
                            media_storage.inspect_upload(self.key_name)
                        elif call == "download":
                            media_storage.download_upload(self.key_name, '"e"', 5, path)
                        else:
                            media_storage.put_playback(f"playback/{uuid4()}/{uuid4()}.mp4", path)
                    except (media_storage.StorageUnavailable, media_storage.ObjectChanged):
                        pass  # the fake origin sends no body for PUT/GET; only the CONNECT matters here
                proxy.close()
                self.assertRegex(proxy.connect, rf"CONNECT {re.escape(HOST)}:443 HTTP/1\.[01]")
