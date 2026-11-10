"""Authenticated, TLS-verified, non-redirecting internal service client.

Peer URLs and signing keys are supplied by secrets/configuration, never Git.
"""
import hashlib
import hmac
import json
import os
import secrets
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPHandler, HTTPSHandler, HTTPRedirectHandler, Request, build_opener

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

def signed_internal_request(audience, path, *, method="GET", payload=b"", timeout=5):
    sender = os.environ["KOLOVIBE_SERVICE_NAME"]
    local = os.environ.get("KOLOVIBE_ENV") == "local"
    if local:
        peers = {name: os.environ.get(f"KOLOVIBE_{name.upper()}_URL")
                 for name in ("identity", "content", "creators", "moderation", "engagement", "points")}
    else:
        peers = json.loads(Path(os.environ["KOLOVIBE_TRUSTED_PEERS_FILE"]).read_text())
    base = peers.get(audience)
    if not isinstance(base, str):
        raise ValueError("Unapproved service audience")
    root = urlsplit(base)
    local_loopback = local and root.scheme == "http" and root.hostname == "127.0.0.1"
    if not (root.scheme == "https" or local_loopback) or not root.hostname or root.username or root.password:
        raise ValueError("Internal service destination must use authenticated TLS")
    if root.path not in ("", "/") or root.query or root.fragment:
        raise ValueError("Peer base URL must be an HTTPS origin without a path")
    if not path.startswith("/internal/") or "?" in path or "#" in path or "\\" in path:
        raise ValueError("Only canonical internal service paths are permitted")
    if not isinstance(payload, bytes):
        raise TypeError("Payload must be pre-serialized bytes")
    key = (os.environ.get("KOLOVIBE_GATEWAY_OUTBOUND_KEY", "") if local else
           Path(os.environ["KOLOVIBE_OUTBOUND_KEY_FILE"]).read_text().strip())
    if len(key) < 32:
        raise RuntimeError("Service signing credential is invalid")
    nonce = secrets.token_urlsafe(24)
    stamp = str(int(time.time()))
    digest = hashlib.sha256(payload).hexdigest()
    canonical = "\n".join((sender, audience, stamp, nonce, method, path, digest))
    signature = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    headers = {
        "X-KoloVibe-Caller": sender,
        "X-KoloVibe-Timestamp": stamp,
        "X-KoloVibe-Nonce": nonce,
        "X-KoloVibe-Signature": signature,
    }
    request = Request(base.rstrip("/") + path, headers=headers,
                      data=payload if method != "GET" else None, method=method)
    ca = os.environ.get("KOLOVIBE_INTERNAL_CA_FILE")
    context = ssl.create_default_context(cafile=ca if ca else None)
    handler = HTTPHandler() if local_loopback else HTTPSHandler(context=context)
    opener = build_opener(handler, _NoRedirect())
    return opener.open(request, timeout=timeout)
