"""Image health probe: verify TLS identity and readiness, without bypassing Host."""

import os
import ssl
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    host = os.environ["KOLOVIBE_ALLOWED_HOSTS"].split(",")[0]
    context = ssl.create_default_context(cafile=os.environ["KOLOVIBE_INTERNAL_CA_FILE"])
    opener = build_opener(HTTPSHandler(context=context), NoRedirect())
    with opener.open(Request(f"https://{host}:8000/health/ready"), timeout=8) as response:
        if response.status != 200 or response.read(100) != b'{"status": "ok"}':
            raise SystemExit("Staging readiness probe failed")


if __name__ == "__main__":
    main()
