"""Authenticate internal service requests; fail closed without approved secrets/database."""
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

def _deny():
    return JsonResponse({"detail": "Forbidden"}, status=403)

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
        secret_file = os.getenv("KOLOVIBE_CALLER_KEYS_FILE")
        service = os.getenv("KOLOVIBE_SERVICE_NAME")
        local_key = os.getenv("KOLOVIBE_CALLER_GATEWAY_KEY") if os.getenv("KOLOVIBE_ENV") == "local" and caller == "gateway" else None
        if not (secret_file or local_key) or not service:
            return _deny()
        try:
            authorized = {caller: local_key} if local_key else json.loads(Path(secret_file).read_text())
            key = authorized.get(caller)
            if not isinstance(key, str) or len(key) < 32:
                return _deny()
            payload_hash = hashlib.sha256(request.body).hexdigest()
            canonical = "\n".join((caller, service, stamp, nonce, request.method,
                                    request.path, payload_hash))
            expected = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
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
        request.service_caller = caller
        return self.get_response(request)
