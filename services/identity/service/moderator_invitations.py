"""Administrator-issued moderator invitations, with mailbox proof and TOTP enrollment."""

import hmac
import json
import logging
import re
import secrets
import smtplib
from datetime import timedelta

import pyotp
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from .accounts import (_body, _bucket, _digest, _email_field, _error,
                       _locked_account, _session_for_access)
from .mfa import cipher, privileged_enabled
from .models import Account, ModeratorInvitation, ModeratorInvitationEvent, RecoveryCode, TotpFactor
from .security_audit import record

logger = logging.getLogger(__name__)
KEY = re.compile(r"[A-Za-z0-9_-]{16,128}")
TOKEN = re.compile(r"[A-Za-z0-9_-]{64}")
GENERIC = "Invalid or unavailable invitation"


def event(kind, invitation=None, actor=None):
    result = record("moderator.invitation_" + kind, actor)
    if invitation is not None:
        ModeratorInvitationEvent.objects.create(event=result, invitation=invitation)


def actor(data, *, fresh=False):
    session = _session_for_access(data.get("access_token"))
    account = _locked_account(session) if session is not None else None
    if account is None:
        return None, _error("Invalid session", 401)
    if (account.role != Account.Role.ADMINISTRATOR or not privileged_enabled()
            or fresh and (session.mfa_verified_at is None
                          or session.mfa_verified_at <= timezone.now() - timedelta(minutes=5))):
        event("denied", actor=account.id)
        return None, _error("Administrator sign-in within the last five minutes required", 403)
    return account, None


def budget(key, limit, now, window=timedelta(hours=1)):
    row = _bucket(_digest("moderator-invitation:" + key), now, window)
    if row.failures >= limit:
        return False
    row.failures += 1
    row.save(update_fields=["failures"])
    return True


def receipt(item):
    return {"id": str(item.id), "status": "pending", "expires_at": item.expires_at.isoformat()}


def summary(item, now):
    state = ("accepted" if item.accepted_at else "revoked" if item.revoked_at
             else "expired" if item.expires_at <= now else "pending")
    row = {"id": str(item.id), "display_name": item.display_name,
           "email_masked": item.email[0] + "***@" + item.email.rsplit("@", 1)[1],
           "status": state, "expires_at": item.expires_at.isoformat()}
    if state == "accepted":
        # Lets an administrator name the moderator when granting queue access; no email or secret.
        row["account_id"] = str(item.accepted_account_id)
    return row


@never_cache
@require_POST
def administer(request):
    try:
        data = _body(request, {"access_token", "operation", "email", "display_name", "reason", "key", "id", "cursor"})
        operation = data.get("operation")
        fields = {"list": {"cursor"}, "create": {"email", "display_name", "reason", "key"},
                  "revoke": {"id", "reason", "key"}}
        if operation not in fields or set(data) - {"access_token", "operation"} - fields[operation]:
            raise ValueError
        if operation != "list" and (not isinstance(data.get("key"), str) or not KEY.fullmatch(data["key"])):
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        return _error("Invalid invitation request")
    try:
        with transaction.atomic():
            administrator, error = actor(data, fresh=operation != "list")
            if error is not None:
                return error
            now = timezone.now()
            if operation == "list":
                rows = ModeratorInvitation.objects.order_by("-created_at", "-id")
                if data.get("cursor"):
                    cursor = rows.filter(pk=data["cursor"]).first()
                    if cursor is None:
                        return _error("Invalid cursor")
                    from django.db.models import Q
                    rows = rows.filter(Q(created_at__lt=cursor.created_at)
                                       | Q(created_at=cursor.created_at, id__lt=cursor.id))
                page = list(rows[:51])
                event("listed", actor=administrator.id)
                return JsonResponse({"items": [summary(item, now) for item in page[:50]],
                                     "next_cursor": str(page[49].id) if len(page) > 50 else None})
            reason = data.get("reason")
            if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
                return _error("A reason of 3 to 500 characters is required")
            if operation == "revoke":
                item = ModeratorInvitation.objects.select_for_update().filter(pk=data.get("id")).first()
                if item is None:
                    return _error("Invitation not found", 404)
                if item.accepted_at:
                    return _error("Invitation already accepted", 409)
                if item.revoked_at is None:
                    item.closed, item.revoked_at, item.revocation_reason = True, now, reason.strip()
                    item.encrypted_secret, item.password_hash = "", ""
                    item.save()
                    event("revoked", item, administrator.id)
                return HttpResponse(status=204)
            email = _email_field(data)
            name = data.get("display_name")
            if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
                return _error("Invalid display name")
            fingerprint = _digest(json.dumps([email, name.strip(), reason.strip()], separators=(",", ":")))
            replay = ModeratorInvitation.objects.filter(created_by=administrator,
                        idempotency_digest=_digest(data["key"])).first()
            if replay is not None:
                if replay.payload_digest != fingerprint:
                    return _error("Idempotency key conflict", 409)
                return JsonResponse(receipt(replay), status=202)
            if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
                return _error("Email delivery unavailable", 503)
            if (not budget("global", 20, now)
                    or not budget(str(administrator.id), 5, now)):
                event("throttled", actor=administrator.id)
                return _error("Too many invitations", 429)
            ModeratorInvitation.objects.filter(email=email, closed=False, expires_at__lte=now).update(
                closed=True, encrypted_secret="", password_hash="")
            if (Account.objects.filter(email=email).exists()
                    or ModeratorInvitation.objects.filter(email=email, closed=False).exists()):
                return _error("Address unavailable for a new invitation", 409)
            if ModeratorInvitation.objects.filter(closed=False, expires_at__gt=now).count() >= 100:
                return _error("Too many pending invitations", 429)
            token = secrets.token_urlsafe(48)
            item = ModeratorInvitation.objects.create(created_by=administrator, email=email,
                display_name=name.strip(), reason=reason.strip(), token_digest=_digest("moderator-invite:" + token),
                idempotency_digest=_digest(data["key"]), payload_digest=fingerprint,
                expires_at=now + timedelta(hours=24))
            # The secret is sent only to the invited mailbox, never to the administrator or a URL.
            send_mail("Your KoloVibe moderator invitation",
                "You have been invited to KoloVibe as a moderator.\n\n"
                "Open the same KoloVibe console used by your administrator and choose Accept moderator invitation.\n"
                "Enter this invitation code with your email address:\n" + token + "\n\n"
                "It expires in 24 hours and works once. You must set your own password and enroll an authenticator. "
                "If you did not expect this invitation, ignore this email.",
                settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            event("created", item, administrator.id)
            return JsonResponse(receipt(item), status=202)
    except (ValidationError, ValueError, TypeError, IntegrityError):
        return _error("Invalid or conflicting invitation", 409)
    except (smtplib.SMTPException, OSError):
        logger.error("Moderator invitation email delivery failed")
        return _error("Email delivery unavailable", 503)


def invitation(data):
    token = data.get("invitation_code")
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return None
    email = _email_field(data)
    found = ModeratorInvitation.objects.filter(token_digest=_digest("moderator-invite:" + token), email=email).first()
    if found is None:
        return None
    # Use the same account-before-invitation lock order as administration.
    inviter = Account.objects.select_for_update().get(pk=found.created_by_id)
    item = ModeratorInvitation.objects.select_for_update().get(pk=found.id)
    if (item.closed or item.expires_at <= timezone.now() or not inviter.is_active
            or inviter.role != Account.Role.ADMINISTRATOR
            or not TotpFactor.objects.filter(account=inviter).exists()):
        return None
    return item


@never_cache
@sensitive_post_parameters("invitation_code", "password", "code")
@require_POST
def accept(request, *, complete=False):
    if not privileged_enabled():
        return _error(GENERIC, 403)
    try:
        data = _body(request, {"invitation_code", "email", "code"} if complete
                     else {"invitation_code", "email", "password"})
        with transaction.atomic():
            item = invitation(data)
            if item is None:
                event("denied")
                return _error(GENERIC, 401)
            now = timezone.now()
            if item.failures >= 5:
                event("throttled", item)
                return _error(GENERIC, 429)
            if Account.objects.filter(email=item.email).exists():
                return _error(GENERIC, 409)
            if not complete:
                password = data.get("password")
                if not isinstance(password, str) or not 12 <= len(password) <= 128:
                    return _error("Invalid password")
                candidate = Account(email=item.email, display_name=item.display_name)
                validate_password(password, user=candidate)
                if (not item.encrypted_secret or item.setup_expires_at <= now):
                    item.encrypted_secret = cipher().encrypt(pyotp.random_base32().encode()).decode()
                    item.password_hash = make_password(password)
                    item.setup_expires_at = min(item.expires_at, now + timedelta(minutes=5))
                    item.save()
                    event("setup_started", item)
                elif not check_password(password, item.password_hash):
                    item.failures += 1
                    item.save(update_fields=["failures"])
                    event("failed", item)
                    return _error(GENERIC, 401)
                secret = cipher().decrypt(item.encrypted_secret.encode()).decode()
                return JsonResponse({"secret": secret, "expires_at": item.setup_expires_at.isoformat()})
            if not item.encrypted_secret or item.setup_expires_at <= now:
                return _error(GENERIC, 401)
            secret = cipher().decrypt(item.encrypted_secret.encode()).decode()
            step = int(now.timestamp()) // 30
            code = data.get("code")
            if (not isinstance(code, str) or re.fullmatch(r"[0-9]{6}", code) is None
                    or not hmac.compare_digest(pyotp.TOTP(secret).at(step * 30), code)):
                item.failures += 1
                item.save(update_fields=["failures"])
                event("failed", item)
                return _error(GENERIC, 401)
            account = Account.objects.create(email=item.email, display_name=item.display_name,
                password=item.password_hash, role=Account.Role.MODERATOR, is_active=True, email_verified_at=now)
            TotpFactor.objects.create(account=account, encrypted_secret=item.encrypted_secret, last_step=step)
            recovery = [secrets.token_urlsafe(32) for _ in range(10)]
            RecoveryCode.objects.bulk_create([RecoveryCode(account=account, digest=_digest("recovery:" + raw)) for raw in recovery])
            item.closed, item.accepted_at, item.accepted_account = True, now, account
            item.encrypted_secret, item.password_hash = "", ""
            item.save()
            event("accepted", item, account.id)
            record("mfa.enrolled", account.id)
            return JsonResponse({"enrolled": True, "recovery_codes": recovery})
    except (KeyError, ValidationError, ValueError, TypeError, IntegrityError):
        return _error(GENERIC, 400)
    except (InvalidToken, RuntimeError):
        logger.error("Moderator invitation MFA configuration unavailable")
        return _error("Enrollment unavailable", 503)
