"""Local first-party account and revocable session operations.

Only the authenticated gateway may call these internal views. Production use is
gated on ADR-013, transport approval, and deployment review.
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import smtplib
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (Account, CodeKind, EmailVerification, LoginSession, LoginThrottle,
                     PasswordReset, ReauthenticationToken, UsedRefreshToken)
from .mfa import challenge, privileged_enabled, session_allowed
from .retention import maybe_purge
from .security_audit import record

ACCESS_SECONDS = 300
REFRESH_DAYS = 30
VERIFY_HOURS = 24  # retired long-token links only (ADR-013 A-1); six-digit codes use VERIFY_MINUTES
VERIFY_MINUTES = 30
RESET_MINUTES = 15
CODE_DIGITS = 6
CODE_ATTEMPTS = 5            # wrong guesses before one issued code is destroyed
CODE_SENDS_PER_HOUR = 3      # emails per account and purpose
CODE_RESEND_COOLDOWN = timedelta(seconds=60)
CODE_ACCOUNT_FAILURES = 10   # wrong guesses per address and purpose across all codes in an hour
CODE_ORIGIN_FAILURES = 40    # wrong guesses per trusted network origin in 15 minutes
CODE_ORIGIN_SENDS = 20       # code emails requested per trusted network origin per hour
CODE_HOUR = timedelta(hours=1)
LOGIN_LIMIT = 5
LOGIN_WINDOW = timedelta(minutes=15)
ACCESS_SALT = "kolovibe.identity.access.v1"
REAUTH_SECONDS = 300
logger = logging.getLogger(__name__)


def _body(request, allowed):
    if len(request.body) > 4096:
        raise ValueError("Request too large")
    data = json.loads(request.body)
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("Invalid request")
    return data


def _error(message, status=400):
    return JsonResponse({"detail": message}, status=status)


def _digest(raw):
    return hmac.new(settings.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()


def _account(account):
    return {"id": str(account.id), "email": account.email,
            "display_name": account.display_name, "roles": [account.role],
            "created_at": account.created_at.isoformat()}


def _issue(session):
    raw = str(session.id) + "." + secrets.token_urlsafe(48)
    session.refresh_digest = _digest(raw)
    session.save(update_fields=["refresh_digest"])
    access = signing.dumps({"sub": str(session.account_id), "sid": str(session.id)},
                           salt=ACCESS_SALT, compress=False)
    return {"access_token": access, "refresh_token": raw,
            "token_type": "Bearer", "expires_in": ACCESS_SECONDS,
            "user": _account(session.account)}


def _session_for_access(token):
    try:
        claims = signing.loads(token, salt=ACCESS_SALT, max_age=ACCESS_SECONDS)
        account_id = uuid.UUID(claims["sub"])
        session_id = uuid.UUID(claims["sid"])
    except (signing.BadSignature, KeyError, TypeError, ValueError, AttributeError):
        return None
    now = timezone.now()
    session = LoginSession.objects.select_related("account").filter(
        pk=session_id, account_id=account_id, revoked_at__isnull=True,
        expires_at__gt=now, account__is_active=True,
    ).first()
    return session if session is not None and session_allowed(session) else None


def _locked_account(session):
    """Serialize account mutations and recheck session state after taking locks."""
    account = Account.objects.select_for_update().get(pk=session.account_id)
    if not account.is_active or not LoginSession.objects.select_for_update().filter(
        pk=session.id, account=account, revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).exists():
        return None
    session.account = account
    return account if session_allowed(session) else None


def _reauthenticate_password(account, password):
    """Account-wide budget for reauthentication, privacy and password changes.

    Count successful attempts too, so token issuance is bounded across sessions.
    The account lock serializes throttle creation and consumption.
    """
    now = timezone.now()
    throttle, _ = LoginThrottle.objects.select_for_update().get_or_create(
        key=_digest("reauth\0" + str(account.id)), defaults={"window_started_at": now})
    if now - throttle.window_started_at >= LOGIN_WINDOW:
        throttle.failures = 0
        throttle.window_started_at = now
    if throttle.failures >= LOGIN_LIMIT:
        record("account.reauthentication_throttled", account.id)
        return _error("Too many attempts", 429)
    throttle.failures += 1
    throttle.save(update_fields=["failures", "window_started_at"])
    if not account.check_password(password):
        record("account.reauthentication_failed", account.id)
        return _error("Reauthentication failed")
    return None


def _consume_reauthentication(account, session, raw):
    now = timezone.now()
    return ReauthenticationToken.objects.filter(
        digest=_digest("reauth:" + raw), account=account, session=session,
        used_at__isnull=True, expires_at__gt=now,
    ).update(used_at=now) == 1


@require_POST
def reauthenticate(request):
    try:
        data = _body(request, {"access_token", "current_password"})
        token, password = data["access_token"], data["current_password"]
        if (not isinstance(token, str) or not isinstance(password, str)
                or not 1 <= len(password) <= 128):
            raise ValueError
    except (KeyError, ValueError, UnicodeError):
        return _error("Reauthentication failed")
    with transaction.atomic():
        session = _session_for_access(token)
        account = _locked_account(session) if session is not None else None
        if account is None:
            return _error("Invalid session", 401)
        error = _reauthenticate_password(account, password)
        if error is not None:
            return error
        raw = secrets.token_urlsafe(48)
        expires_at = timezone.now() + timedelta(seconds=REAUTH_SECONDS)
        ReauthenticationToken.objects.create(
            digest=_digest("reauth:" + raw), account=account, session=session, expires_at=expires_at)
        record("account.reauthenticated", account.id)
    return JsonResponse({"reauth_token": raw, "expires_at": expires_at.isoformat()})


def _throttle_key(email, origin):
    return _digest("login\0" + email + "\0" + origin)


_NIL = uuid.UUID(int=0)
_KIND = {"verify": ("account.verification_code_failed", "account.verification_throttled"),
         "reset": ("account.password_reset_code_failed", "account.password_reset_throttled")}
_CODE_RE = re.compile(r"[0-9]{6}")


def _new_code():
    return "%0*d" % (CODE_DIGITS, secrets.randbelow(10 ** CODE_DIGITS))


def _code_digest(purpose, account_id, issue_id, code):
    """Keyed verifier bound to purpose, account and issue.

    A leaked database row alone cannot be brute-forced offline (the key is derived from the
    service secret), and a code issued for one account, purpose or issue never matches another.
    """
    key = hashlib.sha256(b"kolovibe.identity.code.v1\0" + settings.SECRET_KEY.encode()).digest()
    message = "\0".join((purpose, str(account_id), str(issue_id), code)).encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _issue_code(model, purpose, account, now, lifetime):
    """Create one row and return the raw code for the email; nothing is logged or stored raw."""
    code = _new_code()
    issue_id = uuid.uuid4()
    model.objects.create(
        digest=_code_digest(purpose, account.id, issue_id, code), account=account,
        issue_id=issue_id, kind=CodeKind.CODE, expires_at=now + lifetime, created_at=now)
    return code


def _guard_key(scope, value):
    return _digest("code-guard\0" + scope + "\0" + value)


def _origin(data):
    """Gateway-supplied network origin, or None when the edge cannot vouch for one."""
    value = data.get("origin")
    if value is None:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except (TypeError, ValueError):
        raise ValueError("Invalid origin")


def _bucket(key, now, window):
    throttle, _ = LoginThrottle.objects.select_for_update().get_or_create(
        key=key, defaults={"window_started_at": now})
    if now - throttle.window_started_at >= window:
        throttle.failures = 0
        throttle.window_started_at = now
        throttle.save(update_fields=["failures", "window_started_at"])
    return throttle


def _bucket_full(key, limit, now, window):
    return _bucket(key, now, window).failures >= limit


def _bucket_add(key, now, window):
    throttle = _bucket(key, now, window)
    throttle.failures += 1
    throttle.save(update_fields=["failures"])


def _code_guards(purpose, email, origin):
    guards = [(_guard_key(purpose + "-address", email), CODE_ACCOUNT_FAILURES, CODE_HOUR)]
    if origin is not None:
        guards.append((_guard_key(purpose + "-origin", origin), CODE_ORIGIN_FAILURES,
                       timedelta(minutes=15)))
    return guards


def _send_budget_spent(purpose, origin, now):
    """Count a send request against the trusted origin; True means drop it silently."""
    if origin is None:
        return False
    key = _guard_key(purpose + "-send-origin", origin)
    if _bucket_full(key, CODE_ORIGIN_SENDS, now, CODE_HOUR):
        return True
    _bucket_add(key, now, CODE_HOUR)
    return False


def _send_allowed(model, account, now):
    rows = model.objects.filter(account=account)
    return (rows.exists() and not rows.filter(created_at__gt=now - CODE_RESEND_COOLDOWN).exists()
            and rows.filter(created_at__gt=now - CODE_HOUR).count() < CODE_SENDS_PER_HOUR)


def _send_verification(account, now):
    code = _issue_code(EmailVerification, "verify", account, now, timedelta(minutes=VERIFY_MINUTES))
    send_mail("Your KoloVibe verification code",
              "Your verification code: " + code + "\n\n"
              "It expires in " + str(VERIFY_MINUTES) + " minutes and works once. "
              "KoloVibe will never ask you to share it. "
              "If you did not create an account, ignore this message.",
              settings.DEFAULT_FROM_EMAIL, [account.email], fail_silently=False)


def _spend_guess(guards, now, challenge):
    """Record one wrong guess against every guard and the code that was attacked."""
    for key, _limit, window in guards:
        _bucket_add(key, now, window)
    if challenge is not None:
        challenge.attempts += 1
        if challenge.attempts >= CODE_ATTEMPTS:
            challenge.used_at = now
        challenge.save(update_fields=["attempts", "used_at"])


def _check_code(model, purpose, account, email, raw, origin, now):
    """Return (challenge, response). On success response is None; the caller consumes the row.

    The same work and the same generic answer are produced for an unknown address, a wrong
    code, an expired code and an exhausted code, so the response never reveals which it was.
    """
    guards = _code_guards(purpose, email, origin)
    if any(_bucket_full(key, limit, now, window) for key, limit, window in guards):
        record(_KIND[purpose][1])
        return None, _error("Too many attempts", 429)
    challenge = None
    if account is not None:
        challenge = model.objects.select_for_update().filter(
            account=account, kind=CodeKind.CODE, used_at__isnull=True, expires_at__gt=now,
        ).order_by("-created_at").first()
    expected = challenge.digest if challenge is not None else "0" * 64
    supplied = _code_digest(purpose, account.id if account else _NIL,
                            challenge.issue_id if challenge else _NIL, raw)
    if challenge is None or not hmac.compare_digest(supplied, expected):
        _spend_guess(guards, now, challenge)
        if account is not None:
            record(_KIND[purpose][0], account.id)
        return None, _error("Invalid or expired code")
    return challenge, None


def _email_field(data):
    email = data.get("email")
    if not isinstance(email, str) or len(email) > 254:
        raise ValueError
    email = email.strip().casefold()
    validate_email(email)
    return email


@require_POST
def resend_verification(request):
    try:
        data = _body(request, {"email", "origin"})
        email = _email_field(data)
        origin = _origin(data)
    except (KeyError, ValueError, ValidationError, json.JSONDecodeError):
        return _error("Invalid email address")
    if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
        return _error("Email delivery unavailable", 503)
    try:
        with transaction.atomic():
            now = timezone.now()
            account = Account.objects.select_for_update().filter(
                email=email, is_active=False, email_verified_at__isnull=True,
            ).first()
            if not _send_budget_spent("verify", origin, now) and account is not None \
                    and _send_allowed(EmailVerification, account, now):
                EmailVerification.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
                _send_verification(account, now)
                record("account.verification_resent", account.id)
    except (smtplib.SMTPException, OSError):
        logger.error("Verification resend email delivery failed")
    return HttpResponse(status=204)


@require_POST
def register(request):
    try:
        data = _body(request, {"email", "password", "display_name"})
        email, password, display_name = (data[key] for key in ("email", "password", "display_name"))
        if not all(isinstance(value, str) for value in (email, password, display_name)):
            raise ValueError("Invalid account fields")
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
            return _error("Email delivery unavailable", 503)
        with transaction.atomic():
            account = Account.objects.create_user(email, password, display_name)
            account.is_active = False
            account.save(update_fields=["is_active"])
            _send_verification(account, timezone.now())
            record("account.registered", account.id)
    except (KeyError, ValueError, ValidationError, json.JSONDecodeError):
        return _error("Invalid registration")
    except IntegrityError:
        return _error("Account already exists", 409)
    except (smtplib.SMTPException, OSError):
        logger.error("Account verification email delivery failed")
        return _error("Email delivery unavailable", 503)
    return JsonResponse({"id": str(account.id), "verification_required": True}, status=201)


def _legacy_codes_accepted():
    return getattr(settings, "KOLOVIBE_ACCEPT_LEGACY_LONG_CODES", False)


def _verify_legacy(raw):
    """Pre-A-1 long link. Only rows issued before migration 0010 exist; remove with the flag."""
    with transaction.atomic():
        digest = _digest(raw)
        account_id = EmailVerification.objects.filter(
            digest=digest, kind=CodeKind.TOKEN).values_list("account_id", flat=True).first()
        account = Account.objects.select_for_update().filter(
            pk=account_id, is_active=False, email_verified_at__isnull=True,
        ).first()
        now = timezone.now()
        if account is None or not EmailVerification.objects.filter(
            digest=digest, account=account, kind=CodeKind.TOKEN, used_at__isnull=True,
            expires_at__gt=now,
        ).update(used_at=now):
            return _error("Invalid or expired verification", 400)
        account.is_active = True
        account.email_verified_at = now
        account.save(update_fields=["is_active", "email_verified_at"])
        EmailVerification.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
        record("account.verified", account.id)
    return JsonResponse({"verified": True})


@require_POST
def verify_email(request):
    """Consume a six-digit code. Email verification proves mailbox access; it is not MFA."""
    try:
        data = _body(request, {"email", "code", "origin"})
        raw = data["code"]
        if not isinstance(raw, str):
            raise ValueError("Invalid code")
        if "email" not in data:
            if not _legacy_codes_accepted() or not 32 <= len(raw) <= 128:
                raise ValueError("Invalid code")
            return _verify_legacy(raw)
        email = _email_field(data)
        origin = _origin(data)
        if _CODE_RE.fullmatch(raw) is None:
            raise ValueError("Invalid code")
    except (KeyError, ValueError, ValidationError, json.JSONDecodeError):
        return _error("Invalid verification")
    with transaction.atomic():
        now = timezone.now()
        account = Account.objects.select_for_update().filter(
            email=email, is_active=False, email_verified_at__isnull=True).first()
        challenge, failure = _check_code(EmailVerification, "verify", account, email, raw, origin, now)
        if failure is not None:
            return failure  # returning (not raising) commits the attempt counters
        EmailVerification.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
        account.is_active = True
        account.email_verified_at = now
        account.save(update_fields=["is_active", "email_verified_at"])
        record("account.verified", account.id)
    return JsonResponse({"verified": True})


@require_POST
def request_password_reset(request):
    try:
        data = _body(request, {"email", "origin"})
        email = _email_field(data)
        origin = _origin(data)
    except (KeyError, ValueError, ValidationError, json.JSONDecodeError):
        return _error("Invalid email address")
    if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
        return _error("Email delivery unavailable", 503)
    try:
        with transaction.atomic():
            now = timezone.now()
            account = Account.objects.select_for_update().filter(
                email=email, is_active=True, email_verified_at__isnull=False,
                role__in=(Account.Role.VIEWER, Account.Role.CREATOR),
            ).first()
            if not _send_budget_spent("reset", origin, now) and account is not None:
                rows = PasswordReset.objects.filter(account=account)
                # A first request has no earlier row, so the "has a row" test of resend is skipped.
                if (not rows.filter(created_at__gt=now - CODE_RESEND_COOLDOWN).exists()
                        and rows.filter(created_at__gt=now - CODE_HOUR).count() < CODE_SENDS_PER_HOUR):
                    rows.filter(used_at__isnull=True).update(used_at=now)
                    code = _issue_code(PasswordReset, "reset", account, now,
                                       timedelta(minutes=RESET_MINUTES))
                    send_mail("Your KoloVibe password reset code",
                              "Your password reset code: " + code + "\n\n"
                              "It expires in " + str(RESET_MINUTES) + " minutes and works once. "
                              "KoloVibe will never ask you to share it. "
                              "If you did not ask to reset your password, ignore this message.",
                              settings.DEFAULT_FROM_EMAIL, [account.email], fail_silently=False)
                    record("account.password_reset_requested", account.id)
    except (smtplib.SMTPException, OSError):
        logger.error("Password reset email delivery failed")
        # Delivery errors must not disclose that this address has an account.
    return HttpResponse(status=204)


def _finish_reset(account, password, now):
    validate_password(password, user=account)
    PasswordReset.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
    account.set_password(password)
    account.save(update_fields=["password"])
    LoginSession.objects.filter(account=account, revoked_at__isnull=True).update(revoked_at=now)
    ReauthenticationToken.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
    record("account.password_reset", account.id)


def _reset_legacy(raw, password):
    with transaction.atomic():
        digest = _digest(raw)
        account_id = PasswordReset.objects.filter(
            digest=digest, kind=CodeKind.TOKEN).values_list("account_id", flat=True).first()
        account = Account.objects.select_for_update().filter(
            pk=account_id, is_active=True,
            role__in=(Account.Role.VIEWER, Account.Role.CREATOR),
        ).first()
        now = timezone.now()
        if account is None or not PasswordReset.objects.filter(
            digest=digest, account=account, kind=CodeKind.TOKEN, used_at__isnull=True,
            expires_at__gt=now,
        ).exists():
            return _error("Invalid or expired reset code")
        _finish_reset(account, password, now)
    return HttpResponse(status=204)


@require_POST
def reset_password(request):
    try:
        data = _body(request, {"email", "code", "new_password", "origin"})
        raw, password = data["code"], data["new_password"]
        if (not isinstance(raw, str) or not isinstance(password, str)
                or not 1 <= len(password) <= 128):
            raise ValueError
        if "email" not in data:
            if not _legacy_codes_accepted() or not 32 <= len(raw) <= 128:
                raise ValueError
            return _reset_legacy(raw, password)
        email = _email_field(data)
        origin = _origin(data)
        if _CODE_RE.fullmatch(raw) is None:
            raise ValueError
        with transaction.atomic():
            now = timezone.now()
            account = Account.objects.select_for_update().filter(
                email=email, is_active=True,
                role__in=(Account.Role.VIEWER, Account.Role.CREATOR)).first()
            challenge, failure = _check_code(PasswordReset, "reset", account, email, raw, origin, now)
            if failure is not None:
                return failure
            # A weak new password raises and rolls back, so the right code is not burned.
            _finish_reset(account, password, now)
    except (KeyError, ValueError, ValidationError, json.JSONDecodeError):
        return _error("Invalid password or reset code")
    return HttpResponse(status=204)


@require_POST
def change_password(request):
    try:
        data = _body(request, {"access_token", "current_password", "new_password"})
        token, current, password = (data[key] for key in
                                    ("access_token", "current_password", "new_password"))
        if not all(isinstance(value, str) for value in (token, current, password)):
            raise ValueError
        if not current or len(current) > 128 or not 1 <= len(password) <= 128:
            raise ValueError
        with transaction.atomic():
            session = _session_for_access(token)
            if session is None:
                return _error("Invalid session", 401)
            account = _locked_account(session)
            if account is None:
                return _error("Invalid session", 401)
            error = _reauthenticate_password(account, current)
            if error is not None:
                return error
            validate_password(password, user=account)
            now = timezone.now()
            account.set_password(password)
            account.save(update_fields=["password"])
            LoginSession.objects.filter(account=account, revoked_at__isnull=True).exclude(
                pk=session.id).update(revoked_at=now)
            ReauthenticationToken.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
            record("account.password_changed", account.id)
    except (KeyError, ValueError, ValidationError, json.JSONDecodeError):
        return _error("Invalid password change")
    return HttpResponse(status=204)


@require_POST
def update_profile(request):
    try:
        data = _body(request, {"access_token", "display_name"})
        token, name = data["access_token"], data["display_name"]
        if not isinstance(token, str) or not isinstance(name, str):
            raise ValueError
        name = name.strip()
        if not 2 <= len(name) <= 80:
            raise ValueError
        with transaction.atomic():
            session = _session_for_access(token)
            if session is None:
                return _error("Invalid session", 401)
            account = _locked_account(session)
            if account is None:
                return _error("Invalid session", 401)
            account.display_name = name
            account.save(update_fields=["display_name"])
            record("account.profile_updated", account.id)
    except (KeyError, ValueError, json.JSONDecodeError):
        return _error("Invalid profile")
    return JsonResponse({"user": _account(account)})


@require_POST
def login(request):
    try:
        data = _body(request, {"email", "password"})
        email, password = data["email"], data["password"]
        if not isinstance(email, str) or not isinstance(password, str):
            raise ValueError("Invalid credentials")
        email = email.strip().casefold()
        if len(email) > 254 or len(password) > 128:
            raise ValueError("Invalid credentials")
    except (KeyError, ValueError, json.JSONDecodeError):
        return _error("Invalid credentials", 401)
    key = _throttle_key(email, request.META.get("REMOTE_ADDR", ""))
    now = timezone.now()
    maybe_purge()  # anonymous attempts create throttle rows; keep the table bounded
    with transaction.atomic():
        throttle, _ = LoginThrottle.objects.select_for_update().get_or_create(
            key=key, defaults={"window_started_at": now})
        if now - throttle.window_started_at >= LOGIN_WINDOW:
            throttle.failures = 0
            throttle.window_started_at = now
        if throttle.failures >= LOGIN_LIMIT:
            record("login.throttled")
            return _error("Too many attempts", 429)
        account = authenticate(request, username=email, password=password)
        if account is None or not account.is_active:
            throttle.failures += 1
            throttle.save(update_fields=["failures", "window_started_at"])
            record("login.failed")
            return _error("Invalid credentials", 401)
        if ((account.is_staff or account.is_superuser)
                and account.role not in {Account.Role.MODERATOR, Account.Role.ADMINISTRATOR}):
            return _error("Privileged role configuration unavailable", 403)
        if account.role in {Account.Role.MODERATOR, Account.Role.ADMINISTRATOR}:
            if not privileged_enabled():
                return _error("Privileged access unavailable", 403)
            # Password success must not reset throttling until MFA succeeds.
            throttle.failures += 1
            throttle.save(update_fields=["failures", "window_started_at"])
            return challenge(account, key)
        throttle.failures = 0
        throttle.save(update_fields=["failures", "window_started_at"])
        session = LoginSession.objects.create(
            account=account, authenticated_role=account.role,
            refresh_digest=_digest(secrets.token_urlsafe(48)),
            expires_at=now + timedelta(days=REFRESH_DAYS))
        result = _issue(session)
        record("login.succeeded", account.id)
    return JsonResponse(result)


@require_POST
def refresh(request):
    try:
        data = _body(request, {"refresh_token"})
        raw = data["refresh_token"]
        if not isinstance(raw, str) or not 32 <= len(raw) <= 128:
            raise ValueError("Invalid token")
        session_id = uuid.UUID(raw.split(".", 1)[0])
    except (KeyError, ValueError, json.JSONDecodeError):
        return _error("Invalid session", 401)
    digest = _digest(raw)
    now = timezone.now()
    with transaction.atomic():
        session = LoginSession.objects.select_for_update().select_related("account").filter(pk=session_id).first()
        if session is None or session.revoked_at is not None or session.expires_at <= now or not session.account.is_active:
            return _error("Invalid session", 401)
        if not session_allowed(session):
            return _error("Privileged access unavailable", 403)
        if not hmac.compare_digest(session.refresh_digest, digest):
            if UsedRefreshToken.objects.filter(digest=digest, family_id=session.family_id,
                                               expires_at__gt=now).exists():
                LoginSession.objects.filter(family_id=session.family_id, revoked_at__isnull=True).update(revoked_at=now)
                record("session.replay", session.account_id)
            return _error("Invalid session", 401)
        UsedRefreshToken.objects.create(digest=digest, family_id=session.family_id,
                                        expires_at=session.expires_at)
        session.rotated_at = now
        session.save(update_fields=["rotated_at"])
        result = _issue(session)
        record("session.rotated", session.account_id)
    return JsonResponse(result)


@require_POST
def validate_access(request):
    try:
        data = _body(request, {"access_token", "include_email_verification"})
        token = data["access_token"]
        include_verification = data.get("include_email_verification", False)
        if not isinstance(token, str) or type(include_verification) is not bool:
            raise ValueError("Invalid token")
    except (KeyError, ValueError, json.JSONDecodeError):
        return _error("Invalid session", 401)
    session = _session_for_access(token)
    if session is None:
        return _error("Invalid session", 401)
    result = {"user": _account(session.account), "session_id": str(session.id)}
    if include_verification:
        result["email_verified"] = session.account.email_verified_at is not None
    return JsonResponse(result)


@require_POST
def manage_sessions(request):
    try:
        data = _body(request, {"access_token", "session_id"})
        token = data.get("access_token")
        if not isinstance(token, str):
            raise ValueError
        target = uuid.UUID(data["session_id"]) if "session_id" in data else None
    except (ValueError, TypeError, AttributeError):
        return _error("Invalid session request")
    current = _session_for_access(token)
    if current is None:
        return _error("Invalid session", 401)
    now = timezone.now()
    sessions = LoginSession.objects.filter(
        account_id=current.account_id, revoked_at__isnull=True, expires_at__gt=now,
    )
    with transaction.atomic():
        if _locked_account(current) is None:
            return _error("Invalid session", 401)
        if target is None:
            items = [
                {"id": str(session.id), "created_at": session.created_at.isoformat(),
                 "expires_at": session.expires_at.isoformat(), "current": session.id == current.id}
                for session in sessions.order_by("-created_at", "-id")[:40]
            ]
            record("session.listed", current.account_id)
            return JsonResponse({"items": items})
        if target == current.id:
            return _error("Use sign out to end this session", 409)
        if not sessions.filter(pk=target).update(revoked_at=now):
            return _error("Session not found", 404)
        record("session.revoked", current.account_id)
    return HttpResponse(status=204)


@require_POST
def revoke(request):
    try:
        data = _body(request, {"access_token", "refresh_token"})
        if set(data) not in ({"access_token"}, {"refresh_token"}):
            raise ValueError("Invalid token")
    except (KeyError, ValueError, json.JSONDecodeError):
        return _error("Invalid session", 401)
    if "access_token" in data:
        session = _session_for_access(data["access_token"])
        if session is None:
            return _error("Invalid session", 401)
    else:
        raw = data["refresh_token"]
        try:
            session_id = uuid.UUID(raw.split(".", 1)[0])
        except (AttributeError, TypeError, ValueError):
            return _error("Invalid session", 401)
        session = LoginSession.objects.filter(pk=session_id, refresh_digest=_digest(raw),
                                              revoked_at__isnull=True).first()
        if session is None:
            return _error("Invalid session", 401)
    with transaction.atomic():
        LoginSession.objects.filter(pk=session.id).update(revoked_at=timezone.now())
        record("session.revoked", session.account_id)
    return HttpResponse(status=204)


@require_POST
def standing_context(request):
    """Minimal gateway-only live session context, without personal profile data."""
    if getattr(request, "service_caller", None) != "gateway":
        return _error("Forbidden", 403)
    try:
        data = _body(request, {"access_token"})
        if request.GET or set(data) != {"access_token"} or not isinstance(data["access_token"], str):
            raise ValueError
        session = _session_for_access(data["access_token"])
    except (ValueError, KeyError, TypeError):
        return _error("Invalid session", 401)
    if session is None:
        return _error("Invalid session", 401)
    return JsonResponse({"account_id": str(session.account_id), "account_status": "active",
                         "mfa_verified": session.mfa_verified_at is not None,
                         "email_verified": session.account.email_verified_at is not None})


@require_POST
def sync_creator_role(request):
    """Accept the gateway's live Creator eligibility attestation, never a public role.

    The gateway must bind account_id to a reviewed application or authenticated
    actor and confirm eligibility over its signed Creator connection immediately
    before calling. No other role transition is supported by this operation.
    """
    if getattr(request, "service_caller", None) != "gateway":
        return _error("Forbidden", 403)
    try:
        data = _body(request, {"account_id", "creator_id", "upload_eligible"})
        if request.GET or set(data) != {"account_id", "creator_id", "upload_eligible"}:
            raise ValueError
        account_id = uuid.UUID(data["account_id"])
        uuid.UUID(data["creator_id"])
        if data["upload_eligible"] is not True:
            return _error("Approved creator eligibility required", 403)
    except (ValueError, KeyError, TypeError, AttributeError):
        return _error("Invalid creator transition")
    with transaction.atomic():
        account = Account.objects.select_for_update().filter(pk=account_id).first()
        if (account is None or not account.is_active or account.email_verified_at is None
                or account.is_staff or account.is_superuser
                or account.role not in {Account.Role.VIEWER, Account.Role.CREATOR}):
            return _error("Creator transition forbidden", 403)
        changed = account.role == Account.Role.VIEWER
        if changed:
            account.role = Account.Role.CREATOR
            account.save(update_fields=["role"])
            now = timezone.now()
            LoginSession.objects.filter(account=account, revoked_at__isnull=True).update(revoked_at=now)
            ReauthenticationToken.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
            record("account.creator_role_granted", account.id)
    return JsonResponse({"account_id": str(account.id), "role": "creator", "changed": changed})
