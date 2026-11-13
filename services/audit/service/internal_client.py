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
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

# BEGIN shared service-identity signer (identical in every service; see scripts/test_service_identity_drift.py)
KEY_MIN_LENGTH = 32


def _select_signing_key(audience, peers, local_key=None):
    """Return the credential for exactly one audience; never a key that serves several peers."""
    if local_key is not None:  # local development only (KOLOVIBE_ENV=local)
        key = local_key
    else:
        text = Path(os.environ["KOLOVIBE_OUTBOUND_KEY_FILE"]).read_text().strip()
        if text.startswith("{"):
            keys = json.loads(text)
            if (not isinstance(keys, dict) or not keys
                    or any(not isinstance(value, str) or len(value) < KEY_MIN_LENGTH for value in keys.values())
                    or len(set(keys.values())) != len(keys)):
                raise RuntimeError("Service signing credential is invalid")
            key = keys.get(audience)
            if key is None:
                raise RuntimeError("No signing credential for this service audience")
        elif set(peers) == {audience}:
            key = text  # a single credential is acceptable only when it can serve a single peer
        else:
            raise RuntimeError("A single signing credential cannot serve several service audiences")
    if len(key) < KEY_MIN_LENGTH:
        raise RuntimeError("Service signing credential is invalid")
    return key
# END shared service-identity signer


def signed_internal_request(audience, path, *, method="GET", payload=b"", timeout=5):
    sender = os.environ["KOLOVIBE_SERVICE_NAME"]
    peers = json.loads(Path(os.environ["KOLOVIBE_TRUSTED_PEERS_FILE"]).read_text())
    base = peers.get(audience)
    if not isinstance(base, str):
        raise ValueError("Unapproved service audience")
    root = urlsplit(base)
    if root.scheme != "https" or not root.hostname or root.username or root.password:
        raise ValueError("Internal service destination must use authenticated TLS")
    if root.path not in ("", "/") or root.query or root.fragment:
        raise ValueError("Peer base URL must be an HTTPS origin without a path")
    if not path.startswith("/internal/") or "?" in path or "#" in path or "\\" in path:
        raise ValueError("Only canonical internal service paths are permitted")
    if not isinstance(payload, bytes):
        raise TypeError("Payload must be pre-serialized bytes")
    key = _select_signing_key(audience, peers)
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
    opener = build_opener(HTTPSHandler(context=context), _NoRedirect())
    return opener.open(request, timeout=timeout)
