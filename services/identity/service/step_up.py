"""Decision G: the one step-up mechanism for sensitive actions anywhere on the platform.

A signed-in person re-enters their password to obtain a proof for one named purpose. The proof is a random token
whose digest is stored with the account, the login session, the purpose, the audience (the one service that may
accept it) and, where the purpose requires it, the resource it was obtained for. It lasts PROOF_SECONDS and can be
consumed once.

Only the Gateway may call Identity. It consumes a proof on behalf of the service a request is routed to, using the
same access token as the request, and attests the verified purpose and resource to that service. A proof therefore
cannot be used by another session, another account, another purpose, another service or another resource, and a
replay is refused. A mismatch does not consume the proof, so a mistaken attempt cannot be used to burn someone
else's proof (an attacker would need the token, the session and the bindings).

Issuance shares the account-wide reauthentication budget, so a password guess costs the same here as anywhere.
Services do not implement their own reauthentication: they declare a purpose here and require the attestation.
"""
import re
import secrets
import uuid
from datetime import timedelta

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .accounts import _body, _digest, _error, _locked_account, _reauthenticate_password, _session_for_access
from .models import LoginSession, StepUpProof
from .security_audit import record

PROOF_SECONDS = 300
AUDIENCES = ("identity", "business", "finance", "events", "advertising", "creators", "content", "moderation")

# purpose -> (audience, whether a resource id is required). One line per sensitive action; nothing else is accepted.
PURPOSES = {
    "business.member_remove": ("business", True),
    "business.contact_change": ("business", True),
    "business.close": ("business", True),
    "business.ownership_transfer": ("business", True),
}

_PURPOSE = re.compile(r"[a-z]+\.[a-z_]{1,48}")


def _proof_digest(raw):
    return _digest("step-up:" + raw)


def _uuid_or_none(value, required):
    if value is None:
        if required:
            raise ValueError
        return None
    if not required or not isinstance(value, str):
        raise ValueError
    return uuid.UUID(value)


@require_POST
def issue(request):
    try:
        data = _body(request, {"access_token", "current_password", "purpose", "resource_id"})
        token, password, purpose = data["access_token"], data["current_password"], data["purpose"]
        if (not isinstance(token, str) or not isinstance(password, str) or not 1 <= len(password) <= 128
                or not isinstance(purpose, str) or purpose not in PURPOSES):
            raise ValueError
        audience, needs_resource = PURPOSES[purpose]
        resource = _uuid_or_none(data.get("resource_id"), needs_resource)
    except (KeyError, ValueError, TypeError, UnicodeError, AttributeError):
        return _error("Step-up failed")
    with transaction.atomic():
        session = _session_for_access(token)
        account = _locked_account(session) if session is not None else None
        if account is None:
            return _error("Invalid session", 401)
        error = _reauthenticate_password(account, password)
        if error is not None:
            return error
        raw = secrets.token_urlsafe(48)
        expires_at = timezone.now() + timedelta(seconds=PROOF_SECONDS)
        StepUpProof.objects.create(digest=_proof_digest(raw), account=account, session=session, purpose=purpose,
                                   audience=audience, resource_id=resource, expires_at=expires_at)
        record("account.step_up_issued", account.id)
    return JsonResponse({"step_up_token": raw, "purpose": purpose, "expires_at": expires_at.isoformat()})


@require_POST
def consume(request):
    try:
        data = _body(request, {"access_token", "step_up_token", "purpose", "audience", "resource_id"})
        token, raw, purpose, audience = data["access_token"], data["step_up_token"], data["purpose"], data["audience"]
        if (not isinstance(token, str) or not isinstance(raw, str) or not 32 <= len(raw) <= 128
                or not isinstance(purpose, str) or not _PURPOSE.fullmatch(purpose)
                or purpose not in PURPOSES or audience != PURPOSES[purpose][0]):
            raise ValueError
        resource = _uuid_or_none(data.get("resource_id"), PURPOSES[purpose][1])
    except (KeyError, ValueError, TypeError, UnicodeError, AttributeError):
        return _error("Step-up required", 403)
    with transaction.atomic():
        session = _session_for_access(token)
        if session is None or not LoginSession.objects.select_for_update().filter(
                pk=session.pk, revoked_at__isnull=True, expires_at__gt=timezone.now()).exists():
            return _error("Invalid session", 401)
        now = timezone.now()
        used = StepUpProof.objects.filter(
            digest=_proof_digest(raw), account_id=session.account_id, session=session, purpose=purpose,
            audience=audience, resource_id=resource, used_at__isnull=True, expires_at__gt=now,
        ).update(used_at=now)
        if used != 1:
            record("account.step_up_rejected", session.account_id)
            return _error("Step-up required", 403)
        record("account.step_up_consumed", session.account_id)
    return JsonResponse({"account_id": str(session.account_id), "purpose": purpose,
                         "resource_id": str(resource) if resource else None})
