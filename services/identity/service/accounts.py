"""Local first-party account and revocable session operations.

Only the authenticated gateway may call these internal views. Production use is
gated on ADR-013, transport approval, and deployment review.
"""

import hashlib
import hmac
import json
import logging
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

from .models import Account, EmailVerification, LoginSession, LoginThrottle, PasswordReset, UsedRefreshToken
from .mfa import challenge, privileged_enabled, session_allowed
from .security_audit import record

ACCESS_SECONDS = 300
REFRESH_DAYS = 30
VERIFY_HOURS = 24
RESET_MINUTES = 30
LOGIN_LIMIT = 5
LOGIN_WINDOW = timedelta(minutes=15)
ACCESS_SALT = "kolovibe.identity.access.v1"
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


def _throttle_key(email, origin):
    return _digest("login\0" + email + "\0" + origin)


def _send_verification(account, now):
    raw = secrets.token_urlsafe(48)
    EmailVerification.objects.create(
        digest=_digest(raw), account=account,
        expires_at=now + timedelta(hours=VERIFY_HOURS),
    )
    send_mail("Verify your KoloVibe account",
              "Your verification code: " + raw,
              settings.DEFAULT_FROM_EMAIL, [account.email], fail_silently=False)


@require_POST
def resend_verification(request):
    try:
        data = _body(request, {"email"})
        email = data.get("email")
        if not isinstance(email, str) or len(email) > 254:
            raise ValueError
        email = email.strip().casefold()
        validate_email(email)
    except (ValueError, ValidationError):
        return _error("Invalid email address")
    if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
        return _error("Email delivery unavailable", 503)
    try:
        with transaction.atomic():
            account = Account.objects.select_for_update().filter(
                email=email, is_active=False, email_verified_at__isnull=True,
            ).first()
            if account is not None:
                now = timezone.now()
                codes = EmailVerification.objects.filter(account=account)
                recent = codes.filter(
                    expires_at__gt=now + timedelta(hours=VERIFY_HOURS, minutes=-2),
                )
                if codes.exists() and not recent.exists():
                    codes.filter(used_at__isnull=True).update(used_at=now)
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


@require_POST
def verify_email(request):
    try:
        data = _body(request, {"code"})
        raw = data["code"]
        if not isinstance(raw, str) or not 32 <= len(raw) <= 128:
            raise ValueError("Invalid code")
        with transaction.atomic():
            digest = _digest(raw)
            account_id = EmailVerification.objects.filter(digest=digest).values_list(
                "account_id", flat=True,
            ).first()
            account = Account.objects.select_for_update().filter(
                pk=account_id, is_active=False, email_verified_at__isnull=True,
            ).first()
            now = timezone.now()
            if account is None or not EmailVerification.objects.filter(
                digest=digest, account=account, used_at__isnull=True, expires_at__gt=now,
            ).update(used_at=now):
                return _error("Invalid or expired verification", 400)
            account.is_active = True
            account.email_verified_at = now
            account.save(update_fields=["is_active", "email_verified_at"])
            record("account.verified", account.id)
    except (KeyError, ValueError, json.JSONDecodeError):
        return _error("Invalid verification")
    return JsonResponse({"verified": True})


@require_POST
def request_password_reset(request):
    try:
        data = _body(request, {"email"})
        email = data["email"]
        if not isinstance(email, str) or len(email) > 254:
            raise ValueError
        email = email.strip().casefold()
        validate_email(email)
    except (KeyError, ValueError, ValidationError, json.JSONDecodeError):
        return _error("Invalid email address")
    if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
        return _error("Email delivery unavailable", 503)
    try:
        with transaction.atomic():
            account = Account.objects.select_for_update().filter(
                email=email, is_active=True, email_verified_at__isnull=False,
                role__in=(Account.Role.VIEWER, Account.Role.CREATOR),
            ).first()
            if account is not None:
                now = timezone.now()
                recent = PasswordReset.objects.filter(
                    account=account,
                    expires_at__gt=now + timedelta(minutes=RESET_MINUTES - 2),
                ).exists()
                if not recent:
                    raw = secrets.token_urlsafe(48)
                    PasswordReset.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
                    PasswordReset.objects.create(
                        digest=_digest(raw), account=account,
                        expires_at=now + timedelta(minutes=RESET_MINUTES),
                    )
                    send_mail("Reset your KoloVibe password",
                              "Your password reset code: " + raw,
                              settings.DEFAULT_FROM_EMAIL, [account.email], fail_silently=False)
                    record("account.password_reset_requested", account.id)
    except (smtplib.SMTPException, OSError):
        logger.error("Password reset email delivery failed")
        return _error("Email delivery unavailable", 503)
    return HttpResponse(status=204)


@require_POST
def reset_password(request):
    try:
        data = _body(request, {"code", "new_password"})
        raw, password = data["code"], data["new_password"]
        if (not isinstance(raw, str) or not 32 <= len(raw) <= 128
                or not isinstance(password, str) or not 1 <= len(password) <= 128):
            raise ValueError
        with transaction.atomic():
            digest = _digest(raw)
            account_id = PasswordReset.objects.filter(digest=digest).values_list(
                "account_id", flat=True,
            ).first()
            account = Account.objects.select_for_update().filter(
                pk=account_id, is_active=True,
                role__in=(Account.Role.VIEWER, Account.Role.CREATOR),
            ).first()
            now = timezone.now()
            if account is None or not PasswordReset.objects.filter(
                digest=digest, account=account, used_at__isnull=True,
                expires_at__gt=now,
            ).exists():
                return _error("Invalid or expired reset code")
            validate_password(password, user=account)
            PasswordReset.objects.filter(account=account, used_at__isnull=True).update(used_at=now)
            account.set_password(password)
            account.save(update_fields=["password"])
            LoginSession.objects.filter(account=account, revoked_at__isnull=True).update(revoked_at=now)
            record("account.password_reset", account.id)
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
            account = Account.objects.select_for_update().get(pk=session.account_id)
            if not LoginSession.objects.select_for_update().filter(
                pk=session.id, revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).exists():
                return _error("Invalid session", 401)
            if not account.check_password(current):
                return _error("Invalid current password", 401)
            validate_password(password, user=account)
            now = timezone.now()
            account.set_password(password)
            account.save(update_fields=["password"])
            LoginSession.objects.filter(account=account, revoked_at__isnull=True).update(revoked_at=now)
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
            account = Account.objects.select_for_update().get(pk=session.account_id)
            if not LoginSession.objects.select_for_update().filter(
                pk=session.id, revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).exists():
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
    if target is None:
        return JsonResponse({"items": [
            {"id": str(session.id), "created_at": session.created_at.isoformat(),
             "expires_at": session.expires_at.isoformat(), "current": session.id == current.id}
            for session in sessions.order_by("-created_at", "-id")[:40]
        ]})
    if target == current.id:
        return _error("Use sign out to end this session", 409)
    with transaction.atomic():
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
    return JsonResponse({}, status=204)
