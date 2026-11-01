from datetime import timedelta
import hmac
import logging
import re
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
import pyotp

from .models import Account, LoginSession, LoginThrottle, MfaChallenge, RecoveryCode, TotpFactor
from .security_audit import record

logger = logging.getLogger(__name__)
PRIVILEGED = {Account.Role.MODERATOR, Account.Role.ADMINISTRATOR}
PRIVILEGED_SECONDS = 900


def cipher():
    from staging_runtime import file_value
    try:
        return Fernet(file_value("KOLOVIBE_MFA_ENCRYPTION_KEY_FILE", private=True).encode())
    except (ValueError, RuntimeError):
        raise RuntimeError("MFA encryption configuration unavailable") from None


def privileged_enabled():
    return getattr(settings, "STAGING_PRIVILEGED", False)


def session_allowed(session):
    if session.authenticated_role != session.account.role:
        return False
    if session.account.role not in PRIVILEGED:
        return not (session.account.is_staff or session.account.is_superuser)
    return (privileged_enabled() and session.mfa_verified_at is not None
            and session.mfa_verified_at > timezone.now() - timedelta(seconds=PRIVILEGED_SECONDS)
            and TotpFactor.objects.filter(account_id=session.account_id).exists())


def consume_factor(account, code):
    from .accounts import _digest
    if not isinstance(code, str):
        return None
    factor = TotpFactor.objects.select_for_update().filter(account=account).first()
    if factor is None:
        return None
    if re.fullmatch(r"[0-9]{6}", code):
        try:
            totp = pyotp.TOTP(cipher().decrypt(factor.encrypted_secret.encode()).decode())
        except (InvalidToken, UnicodeError, ValueError):
            raise RuntimeError("MFA encrypted factor unavailable") from None
        step = int(time.time()) // 30
        for candidate in (step, step - 1, step + 1):
            if candidate > factor.last_step and hmac.compare_digest(totp.at(candidate * 30), code):
                factor.last_step = candidate
                factor.save(update_fields=["last_step"])
                return "totp"
        return None
    if not re.fullmatch(r"[a-zA-Z0-9_-]{32,128}", code):
        return None
    recovery = RecoveryCode.objects.select_for_update().filter(
        account=account, digest=_digest("recovery:" + code), used_at__isnull=True).first()
    if recovery is None:
        return None
    recovery.used_at = timezone.now()
    recovery.save(update_fields=["used_at"])
    return "recovery"


def challenge(account, throttle_key):
    from .accounts import _digest
    if not TotpFactor.objects.filter(account=account).exists():
        return JsonResponse({"detail": "Privileged MFA enrollment required"}, status=403)
    raw = secrets.token_urlsafe(48)
    now = timezone.now()
    MfaChallenge.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
    MfaChallenge.objects.create(digest=_digest("challenge:" + raw), account=account,
                               role=account.role, throttle_key=throttle_key,
                               expires_at=now + timedelta(minutes=5))
    record("mfa.challenge", account.id)
    return JsonResponse({"mfa_required": True, "challenge_token": raw, "expires_in": 300},
                        status=202)


@require_POST
def verify_mfa(request):
    from .accounts import _body, _digest, _error, _issue
    if not privileged_enabled():
        return _error("Privileged access unavailable", 403)
    try:
        data = _body(request, {"challenge_token", "code"})
        raw, code = data["challenge_token"], data["code"]
        if not isinstance(raw, str) or not 32 <= len(raw) <= 128 or not isinstance(code, str):
            raise ValueError("Invalid MFA input")
    except (KeyError, ValueError, UnicodeError):
        return _error("Invalid MFA challenge", 401)
    now = timezone.now()
    try:
        with transaction.atomic():
            item = MfaChallenge.objects.select_for_update().select_related("account").filter(
                digest=_digest("challenge:" + raw)).first()
            if (item is None or item.used_at is not None or item.expires_at <= now
                    or not item.account.is_active or item.role != item.account.role
                    or item.role not in PRIVILEGED):
                return _error("Invalid MFA challenge", 401)
            if item.failures >= 5:
                return _error("Too many MFA attempts", 429)
            method = consume_factor(item.account, code)
            if method is None:
                item.failures += 1
                item.save(update_fields=["failures"])
                record("mfa.failed", item.account_id)
                return _error("Invalid MFA code", 401)
            item.used_at = now
            item.save(update_fields=["used_at"])
            LoginThrottle.objects.filter(key=item.throttle_key).update(failures=0)
            session = LoginSession.objects.create(
                account=item.account, authenticated_role=item.role, mfa_verified_at=now,
                refresh_digest=_digest(secrets.token_urlsafe(48)),
                expires_at=now + timedelta(seconds=PRIVILEGED_SECONDS))
            record("mfa.recovery_used" if method == "recovery" else "mfa.succeeded", item.account_id)
            record("login.succeeded", item.account_id)
            return JsonResponse(_issue(session))
    except RuntimeError:
        logger.error("Privileged MFA configuration unavailable")
        return _error("MFA unavailable", 503)
