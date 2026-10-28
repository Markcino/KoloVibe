"""Conservative, non-destructive security probes for an explicitly authorized staging hostname."""
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

url = os.getenv("KOLOVIBE_STAGING_URL", "").rstrip("/")
host = os.getenv("KOLOVIBE_STAGING_HOST", "")
parts = urllib.parse.urlsplit(url)
if parts.scheme != "https" or not parts.hostname or not host:
    raise SystemExit("Set KOLOVIBE_STAGING_URL=https://... and KOLOVIBE_STAGING_HOST explicitly")
if parts.hostname != host or parts.username or parts.password or parts.query or parts.fragment or parts.port not in (None, 443):
    raise SystemExit("The configured URL does not match the authorized staging hostname")
if parts.path not in ("", "/"):
    raise SystemExit("Use a staging site origin, not a path-specific URL")
ctx = ssl.create_default_context()
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

def request(path):
    req = urllib.request.Request(url + path, method="GET", headers={"User-Agent": "KoloVibe-Security-Check/1.0"})
    try:
        with opener.open(req, timeout=8) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code

results = {}
for path in ("/internal", "/internal/health", "/admin"):
    status = request(path)
    results[path] = status
    if status not in (401, 403, 404):
        print(json.dumps({"endpoint": path, "status": status, "error": "Unexpected public response"}))
        raise SystemExit(1)
print(json.dumps({"staging_host": host, "results": results, "status": "basic-public-route-checks-passed"}, indent=2))
print("This does not prove network isolation, origin-bypass prevention, host hardening, or recovery.")
