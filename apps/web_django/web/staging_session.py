"""PostgreSQL-backed web sessions with separately encrypted gateway credentials."""

import json
import uuid
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import WebCredential

IDLE = timedelta(minutes=30)
ABSOLUTE = timedelta(hours=8)


def _cipher():
    return Fernet(settings.WEB_TOKEN_KEY)


def _pack(access, refresh):
    return _cipher().encrypt(json.dumps({"access": access, "refresh": refresh}).encode())


def _unpack(row):
    try:
        tokens = json.loads(_cipher().decrypt(bytes(row.ciphertext)))
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        return None
    if not isinstance(tokens, dict) or set(tokens) != {"access", "refresh"}:
        return None
    if not all(isinstance(value, str) and value for value in tokens.values()):
        return None
    return tokens


def start(request, payload):
    access, refresh = payload.get("access_token"), payload.get("refresh_token")
    if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
        return False
    try:
        identity_session_id = uuid.UUID(refresh.split(".", 1)[0])
    except (ValueError, TypeError):
        return False
    # A second sign-in must invalidate the old browser session and credential row.
    clear(request)
    request.session["authenticated"] = True
    request.session.save()
    now = timezone.now()
    WebCredential.objects.create(
        session_key=request.session.session_key, identity_session_id=identity_session_id,
        ciphertext=_pack(access, refresh), created_at=now, last_activity_at=now,
        absolute_expires_at=now + ABSOLUTE,
    )
    return True


def clear(request):
    if request.session.session_key:
        WebCredential.objects.filter(session_key=request.session.session_key).delete()
    request.session.flush()


def authenticated(request, api):
    """Validate the linked identity session on every protected request."""
    if not request.session.get("authenticated") or not request.session.session_key:
        return 401, {}, None
    with transaction.atomic():
        row = WebCredential.objects.select_for_update().filter(
            session_key=request.session.session_key).first()
        if row is None:
            return 401, {}, None
        now = timezone.now()
        if now >= row.absolute_expires_at or now - row.last_activity_at >= IDLE:
            row.delete()
            return 401, {}, None
        tokens = _unpack(row)
        if tokens is None:
            row.delete()
            return 401, {}, None
        status, account = api("/me", token=tokens["access"])
        if status == 401:
            status, rotated = api("/auth/refresh", method="POST",
                                  data={"refresh_token": tokens["refresh"]})
            if status == 200:
                access, refresh = rotated.get("access_token"), rotated.get("refresh_token")
                if (not isinstance(access, str) or not access
                        or not isinstance(refresh, str) or not refresh
                        or not refresh.startswith(str(row.identity_session_id) + ".")):
                    return 503, {}, None
                row.ciphertext = _pack(access, refresh)
                row.save(update_fields=["ciphertext"])
                status, account = api("/me", token=access)
                tokens = {"access": access, "refresh": refresh}
            elif status == 401:
                row.delete()
                return 401, {}, None
            else:
                return status, {}, None
        if status != 200:
            if status == 401:
                row.delete()
            return status, {}, None
        if now - row.last_activity_at >= timedelta(seconds=60):
            row.last_activity_at = now
            row.save(update_fields=["last_activity_at"])
        return 200, account, tokens["access"]


def refresh_for_logout(request):
    if not request.session.session_key:
        return None
    row = WebCredential.objects.filter(session_key=request.session.session_key).first()
    tokens = _unpack(row) if row else None
    return tokens["refresh"] if tokens else None
