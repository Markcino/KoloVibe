"""Read-only checks against an explicitly authorized, HTTPS-only KoloVibe environment.

A scoped token is sent ONLY to a predetermined same-origin HTTPS endpoint. It is never
sent on redirects or used for anonymous negative-route checks.
"""
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

url = os.getenv("KOLOVIBE_STAGING_URL", "").rstrip("/")
host = os.getenv("KOLOVIBE_STAGING_HOST", "").strip()
path = os.getenv("KOLOVIBE_STAGING_CHECK_PATH", "").strip()
token = os.getenv("KOLOVIBE_STAGING_CHECK_TOKEN", "")
parts = urllib.parse.urlsplit(url)
if parts.scheme != "https" or not parts.hostname or not host:
    raise SystemExit("An authorized HTTPS staging origin and hostname must be configured")
if (
    parts.hostname != host
    or parts.username
    or parts.password
    or parts.query
    or parts.fragment
    or parts.port not in (None, 443)
    or parts.path not in ("", "/")
):
    raise SystemExit("Staging origin must exactly match the approved hostname on HTTPS port 443")
if (
    not path.startswith("/")
    or path.startswith("//")
    or "?" in path
    or "#" in path
    or "\\" in path
    or "/../" in path
    or "/./" in path
    or path.endswith("/..")
    or path.endswith("/.")
    or "%" in path
):
    raise SystemExit("Probe path must be an absolute, normalized same-origin path")
if not token or len(token) < 24 or "\n" in token or "\r" in token:
    raise SystemExit("Missing or invalid protected environment probe token")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    NoRedirect(),
)

def request(relative, auth=False):
    headers = {"User-Agent": "KoloVibe-Security-Check/1.0"}
    if auth:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url + relative, method="GET", headers=headers)
    try:
        with opener.open(req, timeout=8) as response:
            status = response.status
            data = response.read(4096)
            return status, data
    except urllib.error.HTTPError as exc:
        return exc.code, b""

# Authenticated endpoint must be explicitly configured and must return a recognizable
# JSON health contract. Do not print secret-bearing response headers or bodies.
status, body = request(path, auth=True)
if status != 200:
    raise SystemExit(f"Authenticated environment verification failed (HTTP {status})")
try:
    response = json.loads(body)
except (ValueError, UnicodeDecodeError):
    raise SystemExit("Authenticated environment verification did not return JSON")
if response != {"status": "ok"}:
    raise SystemExit("Authenticated environment verification returned an unexpected response")

results = {}
for relative in ("/internal", "/internal/health", "/admin"):
    if relative == path:
        raise SystemExit("The protected probe endpoint may not be an anonymous-negative route")
    status, _ = request(relative)
    results[relative] = status
    if status not in (401, 403, 404):
        raise SystemExit(f"Unexpected public response on reserved route (HTTP {status})")

print(json.dumps({"staging_host": host, "authenticated_probe": "passed",
                  "anonymous_route_statuses": results}, indent=2))
print("Application-level results do not establish infrastructure network isolation or backup recovery.")
