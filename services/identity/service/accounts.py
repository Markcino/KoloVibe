"""Local first-party account and revocable session operations.

Only the authenticated gateway may call these internal views. Production use is
gated on ADR-013, transport approval, and deployment review.
"""

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Account, EmailVerification, LoginSession, LoginThrottle, UsedRefreshToken

ACCESS_SECONDS = 300
REFRESH_DAYS = 30
VERIFY_HOURS = 24
LOGIN_LIMIT = 5
LOGIN_WINDOW = timedelta(minutes=15)
ACCESS_SALT = "kolovibe.identity.access.v1"


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
    return LoginSession.objects.select_related("account").filter(
        pk=session_id, account_id=account_id, revoked_at__isnull=True,
        expires_at__gt=now, account__is_active=True,
    ).first()


def _throttle_key(email, origin):
    return _digest("login\0" + email + "\0" + origin)


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
            raw = secrets.token_urlsafe(48)
            EmailVerification.objects.create(
                digest=_digest(raw), account=account,
                expires_at=timezone.now() + timedelta(hours=VERIFY_HOURS),
            )
            send_mail("Verify your KoloVibe account",
                      "Your verification code: " + raw,
                      settings.DEFAULT_FROM_EMAIL, [account.email], fail_silently=False)
    except (KeyError, ValueError, ValidationError, json.JSONDecodeError):
        return _error("Invalid registration")
    except IntegrityError:
        return _error("Account already exists", 409)
    except Exception:
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
            verification = EmailVerification.objects.select_for_update().select_related("account").filter(
                digest=_digest(raw), used_at__isnull=True, expires_at__gt=timezone.now()).first()
            if verification is None:
                return _error("Invalid or expired verification", 400)
            verification.used_at = timezone.now()
            verification.save(update_fields=["used_at"])
            verification.account.is_active = True
            verification.account.save(update_fields=["is_active"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return _error("Invalid verification")
    return JsonResponse({"verified": True})


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
            return _error("Too many attempts", 429)
        account = authenticate(request, username=email, password=password)
        if account is None or not account.is_active:
            throttle.failures += 1
            throttle.save(update_fields=["failures", "window_started_at"])
            return _error("Invalid credentials", 401)
        if account.role in {Account.Role.MODERATOR, Account.Role.ADMINISTRATOR}:
            return _error("Privileged access unavailable", 403)
        throttle.failures = 0
        throttle.save(update_fields=["failures", "window_started_at"])
        session = LoginSession.objects.create(
            account=account, refresh_digest=_digest(secrets.token_urlsafe(48)),
            expires_at=now + timedelta(days=REFRESH_DAYS))
        result = _issue(session)
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
        if not hmac.compare_digest(session.refresh_digest, digest):
            if UsedRefreshToken.objects.filter(digest=digest, family_id=session.family_id,
                                               expires_at__gt=now).exists():
                LoginSession.objects.filter(family_id=session.family_id, revoked_at__isnull=True).update(revoked_at=now)
            return _error("Invalid session", 401)
        UsedRefreshToken.objects.create(digest=digest, family_id=session.family_id,
                                        expires_at=session.expires_at)
        session.rotated_at = now
        session.save(update_fields=["rotated_at"])
        result = _issue(session)
    return JsonResponse(result)


@require_POST
def validate_access(request):
    try:
        token = _body(request, {"access_token"})["access_token"]
        if not isinstance(token, str):
            raise ValueError("Invalid token")
    except (KeyError, ValueError, json.JSONDecodeError):
        return _error("Invalid session", 401)
    session = _session_for_access(token)
    if session is None:
        return _error("Invalid session", 401)
    if session.account.role in {Account.Role.MODERATOR, Account.Role.ADMINISTRATOR}:
        return _error("Privileged access unavailable", 403)
    return JsonResponse({"user": _account(session.account), "session_id": str(session.id)})


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
    LoginSession.objects.filter(pk=session.id).update(revoked_at=timezone.now())
    return JsonResponse({}, status=204)
