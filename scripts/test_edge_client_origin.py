"""D12-001 and T10_81/T10_87: the edge limits requests and hands the Gateway a client address it can trust.

Static checks always run. The live checks start the real Nginx on the rendered API template with a local
HTTPS echo upstream; they run wherever an `nginx` binary is installed and are skipped (with the reason)
elsewhere. Run: python -m unittest scripts.test_edge_client_origin
"""
import http.client
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ops"))
import kolovibe_cluster as cluster  # noqa: E402

HEADER = "CF-Connecting-IP"
API_TEMPLATE = ROOT / "infra/nginx/staging.conf.template"
WEB_VHOST = ROOT / "infra/nginx/kolovibe-web-staging.conf"
NAMED_INPUTS = {"ORIGIN_CERT_FILE", "ORIGIN_KEY_FILE", "GATEWAY_PRIVATE_ENDPOINT", "GATEWAY_TLS_NAME",
                "INTERNAL_CA_FILE", "TUNNEL_CONNECTOR_ADDRESS"}


class StaticEdgeConfiguration(unittest.TestCase):
    def test_T10_81_every_repository_vhost_defines_request_and_connection_limits(self):
        for path in (API_TEMPLATE, WEB_VHOST):
            text = path.read_text()
            with self.subTest(path.name):
                zones = re.findall(r"limit_req_zone \$binary_remote_addr zone=(\w+):", text)
                self.assertEqual(len(zones), 1)
                self.assertIn(f"limit_req zone={zones[0]} ", text)
                self.assertRegex(text, r"limit_conn_zone \$binary_remote_addr zone=(\w+):")
                self.assertRegex(text, r"\n\s+limit_conn \w+ \d+;")
                self.assertIn("limit_req_status 429;", text)

    def test_T10_87_gateway_deployments_trust_the_header_the_edge_overwrites(self):
        stack = yaml.safe_load((ROOT / "infra/swarm/staging.yml").read_text())
        self.assertEqual(stack["services"]["gateway"]["environment"]["KOLOVIBE_TRUSTED_CLIENT_IP_HEADER"], HEADER)
        # The AWS Gateway is changed only through the cluster tool's reviewed R1 rollout.
        self.assertEqual(cluster.r1_rollout_table()["gateway"]["env"], {"KOLOVIBE_TRUSTED_CLIENT_IP_HEADER": HEADER})
        for service, rollout in cluster.r1_rollout_table().items():
            if service != "gateway":
                self.assertNotIn("KOLOVIBE_TRUSTED_CLIENT_IP_HEADER", rollout["env"], service)

    def test_edge_overwrites_the_trusted_header_and_believes_it_only_from_the_connector(self):
        for path, connector in ((API_TEMPLATE, "${TUNNEL_CONNECTOR_ADDRESS}"), (WEB_VHOST, "127.0.0.1")):
            text = path.read_text()
            with self.subTest(path.name):
                self.assertEqual(re.findall(r"set_real_ip_from (\S+);", text), [connector])
                self.assertIn(f"real_ip_header {HEADER};", text)
                self.assertIn("real_ip_recursive off;", text)
                self.assertIn(f"proxy_set_header {HEADER} $remote_addr;", text)
                self.assertIn('proxy_set_header X-Forwarded-For "";', text)
        self.assertIn("listen 127.0.0.1:80;", WEB_VHOST.read_text())  # its only peer is the local connector

    def test_api_template_uses_only_named_inputs(self):
        self.assertEqual(set(re.findall(r"\$\{([A-Z_]+)\}", API_TEMPLATE.read_text())), NAMED_INPUTS)


class _Echo(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"client": self.headers.get(HEADER), "xff": self.headers.get("X-Forwarded-For"),
                           "real": self.headers.get("X-Real-IP"), "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(shutil.which("nginx"), "nginx is not installed here; the static checks above still ran")
class LiveApiEdge(unittest.TestCase):
    """The rendered API template on a real Nginx in front of an HTTPS echo standing in for the Gateway."""

    def start(self, connector):
        work = Path(tempfile.mkdtemp(prefix="kv-edge-"))
        self.addCleanup(shutil.rmtree, work, True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=gateway",
                        "-addext", "subjectAltName=DNS:gateway,IP:127.0.0.1",
                        "-keyout", str(work / "key.pem"), "-out", str(work / "cert.pem")],
                       check=True, capture_output=True)
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Echo)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(work / "cert.pem", work / "key.pem")
        upstream.socket = context.wrap_socket(upstream.socket, server_side=True)
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        self.addCleanup(upstream.server_close)
        self.addCleanup(upstream.shutdown)
        self.client_context = ssl.create_default_context(cafile=str(work / "cert.pem"))
        inputs = {"ORIGIN_CERT_FILE": work / "cert.pem", "ORIGIN_KEY_FILE": work / "key.pem",
                  "GATEWAY_PRIVATE_ENDPOINT": f"127.0.0.1:{upstream.server_address[1]}", "GATEWAY_TLS_NAME": "gateway",
                  "INTERNAL_CA_FILE": work / "cert.pem", "TUNNEL_CONNECTOR_ADDRESS": connector}
        rendered = API_TEMPLATE.read_text()
        for name, value in inputs.items():
            rendered = rendered.replace("${" + name + "}", str(value))
        self.port = _free_port()
        # Test-only changes: an unprivileged port and a writable log path. Everything else is as shipped.
        rendered = rendered.replace("listen 443 ssl", f"listen 127.0.0.1:{self.port} ssl")
        rendered = rendered.replace("/var/log/nginx/kolovibe-error.log", str(work / "error.log"))
        (work / "api.conf").write_text(rendered)
        (work / "nginx.conf").write_text(
            f"pid {work}/nginx.pid; error_log {work}/main.log; daemon on;\nevents {{}}\n"
            f"http {{ access_log off; client_body_temp_path {work}; proxy_temp_path {work}; "
            f"include {work}/api.conf; }}\n")
        subprocess.run(["nginx", "-t", "-q", "-p", str(work), "-c", str(work / "nginx.conf")], check=True)
        subprocess.run(["nginx", "-p", str(work), "-c", str(work / "nginx.conf")], check=True)
        self.addCleanup(subprocess.run, ["nginx", "-p", str(work), "-c", str(work / "nginx.conf"), "-s", "stop"])
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", self.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)

    def get(self, path, **headers):
        connection = http.client.HTTPSConnection("127.0.0.1", self.port, context=self.client_context,
                                                 timeout=5)
        connection.request("GET", path, headers={"Host": "api.cabetechs.shop", **headers})
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return response.status, (json.loads(body) if response.status == 200 else None)

    def test_client_address_from_the_connector_reaches_the_gateway_and_spoofed_copies_do_not(self):
        self.start(connector="127.0.0.1")
        status, seen = self.get("/videos", **{HEADER: "203.0.113.7", "X-Forwarded-For": "198.51.100.1",
                                               "X-Real-IP": "198.51.100.2"})
        self.assertEqual(status, 200)
        self.assertEqual(seen, {"client": "203.0.113.7", "xff": None, "real": None, "path": "/videos"})
        # The quoted route regex accepts a UUID path and everything else, including accounts, stays closed.
        status, _ = self.get("/api/v1/videos/" + "0" * 8 + "-0000-0000-0000-" + "0" * 12)
        self.assertEqual(status, 200)
        self.assertEqual(self.get("/api/v1/auth/register")[0], 403)

    def test_a_peer_that_is_not_the_connector_cannot_choose_its_address(self):
        self.start(connector="192.0.2.10")  # this test's client (127.0.0.1) is not the connector
        status, seen = self.get("/videos", **{HEADER: "203.0.113.7"})
        self.assertEqual((status, seen["client"]), (200, "127.0.0.1"))

    def test_a_flood_from_one_client_is_refused_and_another_client_is_unaffected(self):
        self.start(connector="127.0.0.1")
        statuses = [self.get("/videos", **{HEADER: "203.0.113.7"})[0] for _ in range(40)]
        self.assertIn(429, statuses)
        self.assertEqual(set(statuses), {200, 429})
        self.assertEqual(self.get("/videos", **{HEADER: "203.0.113.8"})[0], 200)


if __name__ == "__main__":
    unittest.main()
