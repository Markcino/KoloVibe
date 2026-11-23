"""Authenticate internal service requests; fail closed without approved secrets/database.

Every caller has its own credential and this service accepts only the callers and paths named in
CALLER_PATHS, so a key held by one service cannot sign as another service.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import time
from pathlib import Path
from django.db import DatabaseError, connection, transaction
from django.http import JsonResponse

# caller -> exact paths ("/x") or path prefixes ("/x/") that caller may reach on this service.
CALLER_PATHS = {
    "gateway": ('/internal/probe', '/internal/audit/read'),
    "identity": ('/internal/security-events',),
    "moderation": ('/internal/security-events',),
    "creators": ('/internal/security-events',),
    "content": ('/internal/security-events',),
    "points": ('/internal/security-events',),
}

# BEGIN shared service-identity verifier (identical in every service; see scripts/test_service_identity_drift.py)
KEY_MIN_LENGTH = 32
MAX_KEYS_PER_CALLER = 2  # one active key, plus one previous key during a rotation overlap


def _deny():
    return JsonResponse({"detail": "Forbidden"}, status=403)


def _path_allowed(caller, path):
    return any(path == rule or (rule.endswith("/") and path.startswith(rule))
               for rule in CALLER_PATHS.get(caller, ()))


def _local_key(caller):
    """Local development only: single-process keys injected through the environment."""
    if os.getenv("KOLOVIBE_ENV") != "local":
        return None
    if caller == "gateway":
        return os.getenv("KOLOVIBE_CALLER_GATEWAY_KEY")
    if caller == "moderation":
        return os.getenv("KOLOVIBE_CALLER_MODERATION_KEY")
    return None


def _accepted_keys(caller, secret_file):
    """Return the keys that may sign for `caller`, or None when the configuration is unsafe."""
    local_key = _local_key(caller)
    if local_key:
        return [local_key] if len(local_key) >= KEY_MIN_LENGTH else None
    if not secret_file:
        return None
    authorized = json.loads(Path(secret_file).read_text())
    if not isinstance(authorized, dict):
        return None
    every_key = []
    for value in authorized.values():
        keys = value if isinstance(value, list) else [value]
        if not 1 <= len(keys) <= MAX_KEYS_PER_CALLER:
            return None
        if any(not isinstance(key, str) or len(key) < KEY_MIN_LENGTH for key in keys):
            return None
        every_key.extend(keys)
    if len(set(every_key)) != len(every_key):
        return None  # a credential shared by two callers (or entries) would let them impersonate each other
    value = authorized.get(caller)
    return None if value is None else (value if isinstance(value, list) else [value])


# A signed request is accepted for 60 seconds, so a nonce older than the retention below can never match a valid
# timestamp and is safe to forget. Without this the table grows by one row per internal request, forever.
NONCE_RETENTION_MINUTES = 10
NONCE_PURGE_INTERVAL = 60.0  # seconds, per process
NONCE_PURGE_BATCH = 5000
_nonce_purge = {"at": None}


def _purge_expired_nonces():
    """Delete one bounded batch of expired nonces, at most once a minute; never fails a valid request."""
    now = time.monotonic()
    if _nonce_purge["at"] is not None and now - _nonce_purge["at"] < NONCE_PURGE_INTERVAL:
        return
    _nonce_purge["at"] = now
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                cursor.execute(
                    "DELETE FROM internal_request_nonce WHERE ctid IN (SELECT ctid FROM internal_request_nonce "
                    "WHERE received_at < CURRENT_TIMESTAMP - make_interval(mins => %s) LIMIT %s)",
                    [NONCE_RETENTION_MINUTES, NONCE_PURGE_BATCH])
            else:
                cursor.execute(
                    "DELETE FROM internal_request_nonce WHERE rowid IN (SELECT rowid FROM internal_request_nonce "
                    "WHERE received_at < datetime('now', %s) LIMIT %s)",
                    [f"-{int(NONCE_RETENTION_MINUTES)} minutes", NONCE_PURGE_BATCH])
    except DatabaseError:
        logging.getLogger(__name__).error("Internal nonce purge unavailable")


class ServiceAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/internal/"):
            return self.get_response(request)
        caller = request.headers.get("X-KoloVibe-Caller", "")
        nonce = request.headers.get("X-KoloVibe-Nonce", "")
        stamp = request.headers.get("X-KoloVibe-Timestamp", "")
        sig = request.headers.get("X-KoloVibe-Signature", "")
        if not re.fullmatch(r"[a-z]{2,32}", caller):
            return _deny()
        if not re.fullmatch(r"[a-zA-Z0-9_-]{16,100}", nonce):
            return _deny()
        if not re.fullmatch(r"[0-9]{10}", stamp) or not re.fullmatch(r"[0-9a-f]{64}", sig):
            return _deny()
        if abs(time.time() - int(stamp)) > 60:
            return _deny()
        if not _path_allowed(caller, request.path):
            return _deny()
        secret_file = os.getenv("KOLOVIBE_CALLER_KEYS_FILE")
        service = os.getenv("KOLOVIBE_SERVICE_NAME")
        if not service:
            return _deny()
        try:
            keys = _accepted_keys(caller, secret_file)
            if not keys:
                return _deny()
            payload_hash = hashlib.sha256(request.body).hexdigest()
            canonical = "\n".join((caller, service, stamp, nonce, request.method,
                                    request.path, payload_hash))
            matched = False
            for key in keys:
                expected = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
                matched = hmac.compare_digest(sig, expected) or matched
            if not matched:
                return _deny()
        except (OSError, ValueError, TypeError):
            logging.getLogger(__name__).error("Internal caller configuration unavailable")
            return _deny()
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO internal_request_nonce (caller,nonce) "
                        "VALUES (%s,%s) ON CONFLICT DO NOTHING", [caller, nonce]
                    )
                    if cursor.rowcount != 1:
                        return _deny()
        except DatabaseError:
            logging.getLogger(__name__).error("Internal nonce database unavailable")
            return JsonResponse({"detail": "Service unavailable"}, status=503)
        _purge_expired_nonces()
        request.service_caller = caller
        return self.get_response(request)
# END shared service-identity verifier
