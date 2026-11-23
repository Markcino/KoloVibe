"""PostgreSQL-backed web sessions with separately encrypted gateway credentials."""

import json
import uuid
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import WebCredential
from .api_contracts import valid_id

IDLE = timedelta(minutes=30)
PRIVILEGED_ABSOLUTE = timedelta(minutes=15)
MFA_CHALLENGE_SECONDS = 300
MFA_PENDING = "pending_mfa"


def privileged_account(account):
    return (isinstance(account, dict)
            and valid_id(account.get("id"))
            and account.get("roles") in (["moderator"], ["administrator"]))


def begin_mfa(request, payload, email):
    """Keep the password-proven challenge encrypted on the server, never in a form or URL."""
    raw, lifetime = payload.get("challenge_token"), payload.get("expires_in")
    if (payload.get("mfa_required") is not True or not isinstance(raw, str)
            or not 32 <= len(raw) <= 128 or type(lifetime) is not int
            or not 0 < lifetime <= MFA_CHALLENGE_SECONDS
            or not isinstance(email, str) or not email.strip()):
        return False
    clear(request)
    state = {"challenge_token": raw, "email": email.strip().casefold(),
             "expires_at": timezone.now().timestamp() + lifetime}
    request.session[MFA_PENDING] = _cipher().encrypt(json.dumps(state).encode()).decode()
    request.session.set_expiry(lifetime)
    return True


def pending_mfa(request):
    raw = request.session.get(MFA_PENDING)
    if not isinstance(raw, str):
        return None
    try:
        state = json.loads(_cipher().decrypt(raw.encode()))
        if (not isinstance(state, dict) or set(state) != {"challenge_token", "email", "expires_at"}
                or not isinstance(state["challenge_token"], str)
                or not 32 <= len(state["challenge_token"]) <= 128
                or not isinstance(state["email"], str)
                or type(state["expires_at"]) not in (int, float)
                or not timezone.now().timestamp() < state["expires_at"]
                <= timezone.now().timestamp() + MFA_CHALLENGE_SECONDS):
            raise ValueError("Invalid challenge state")
        return state
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        request.session.pop(MFA_PENDING, None)
        return None


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


def start(request, payload, *, mfa_verified=False):
    account = payload.get("user")
    privileged = privileged_account(account)
    if not (privileged and mfa_verified):
        return False
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
    request.session["mfa_verified"] = True
    request.session["authenticated_role"] = account["roles"][0]
    request.session["authenticated_account"] = account["id"]
    lifetime = PRIVILEGED_ABSOLUTE
    now = timezone.now()
    # Shown to the user so a session never ends by surprise; the database row stays the authority.
    request.session["session_ends_at"] = (now + lifetime).isoformat()
    request.session.set_expiry(int(lifetime.total_seconds()))
    request.session.save()
    WebCredential.objects.create(
        session_key=request.session.session_key, identity_session_id=identity_session_id,
        ciphertext=_pack(access, refresh), created_at=now, last_activity_at=now,
        absolute_expires_at=now + lifetime,
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
        if (now >= row.absolute_expires_at or now - row.created_at >= PRIVILEGED_ABSOLUTE
                or now - row.last_activity_at >= IDLE):
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
            elif status in (401, 403):
                row.delete()
                return 401, {}, None
            else:
                return status, {}, None
        if status != 200:
            if status in (401, 403):
                row.delete()
                return 401, {}, None
            return status, {}, None
        role = request.session.get("authenticated_role")
        if not privileged_account(account):
            row.delete()
            return 403, {}, None
        if (account["roles"] != [role] or request.session.get("mfa_verified") is not True
                or account["id"] != request.session.get("authenticated_account")):
            row.delete()
            return 401, {}, None
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

