"""Internal operation dispatcher: the only HTTP surface of the Business service.

The Gateway authenticates the caller against Identity and forwards a signed envelope; this service re-validates
every field, applies per-object authorization (authz.py), throttles, replays idempotent results, and returns
only allowlisted shapes. Nothing in the envelope names authority except the gateway-attested actor and role.
"""
import hashlib
import hmac
import json
import logging
import re
from dataclasses import dataclass, field

from django.conf import settings
from django.db import DatabaseError, IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache

from . import throttle
from .errors import ApiError
from .models import IdempotencyRecord
from .validation import uuid_text

logger = logging.getLogger(__name__)
ENVELOPE = {"actor_id", "role", "mfa_verified", "email_verified", "idempotency_key", "data"}
KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")
MAX_BODY = 8192
OPERATIONS = {}


@dataclass
class Context:
    actor_id: object
    role: str
    mfa_verified: bool
    email_verified: bool
    idempotency_key: str | None


@dataclass
class Result:
    status: int
    body: dict
    secret: dict = field(default_factory=dict)  # returned once, never stored or replayed


@dataclass
class Operation:
    name: str
    handler: object
    roles: tuple
    mfa: bool
    verified_email: bool
    idempotent: bool
    budget: str | None


def operation(name, *, roles, mfa=False, verified_email=False, idempotent=False, budget=None):
    def register(handler):
        OPERATIONS[name] = Operation(name, handler, tuple(roles), mfa, verified_email, idempotent, budget)
        return handler
    return register


def _error(status, detail, code=None):
    body = {"detail": detail}
    if code:
        body["code"] = code
    return JsonResponse(body, status=status)


def _respond(result, extra=None):
    if result.status == 204:
        return HttpResponse(status=204)
    return JsonResponse({**result.body, **(extra or {})}, status=result.status)


def _digest(*parts):
    return hmac.new(settings.SECRET_KEY.encode(), "\0".join(parts).encode(), hashlib.sha256).hexdigest()


def _run(op, ctx, data):
    if not op.idempotent:
        return op.handler(ctx, data), {}
    if ctx.idempotency_key is None or not KEY_PATTERN.fullmatch(ctx.idempotency_key):
        raise ApiError(400, "A valid Idempotency-Key is required")
    key = _digest("idem", ctx.idempotency_key)
    payload = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    lookup = {"actor_id": ctx.actor_id, "operation": op.name, "key_digest": key}

    def replay(record):
        if record.payload_digest != payload:
            raise ApiError(409, "Idempotency-Key was used with a different request", "idempotency_conflict")
        return Result(record.status, record.body), {}

    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.select_for_update().filter(**lookup).first()
            if record is not None:
                return replay(record)
            result = op.handler(ctx, data)
            IdempotencyRecord.objects.create(**lookup, payload_digest=payload, status=result.status, body=result.body)
            return result, result.secret
    except IntegrityError:  # a concurrent first request won the key; its recorded result is the answer
        record = IdempotencyRecord.objects.filter(**lookup).first()
        if record is None:
            raise
        return replay(record)


@never_cache
def dispatch(request, operation):
    if request.method != "POST":
        return _error(405, "Method not allowed")
    if getattr(request, "service_caller", None) != "gateway":
        return _error(403, "Forbidden")
    op = OPERATIONS.get(operation)
    try:
        if op is None or request.GET or len(request.body) > MAX_BODY:
            return _error(404 if op is None else 400, "Not found" if op is None else "Invalid request")
        envelope = json.loads(request.body)
        if not isinstance(envelope, dict) or set(envelope) != ENVELOPE:
            raise ValueError
        key = envelope["idempotency_key"]
        if (type(envelope["mfa_verified"]) is not bool or type(envelope["email_verified"]) is not bool
                or not isinstance(envelope["role"], str) or not isinstance(envelope["data"], dict)
                or (key is not None and not isinstance(key, str))):
            raise ValueError
        ctx = Context(uuid_text(envelope["actor_id"]), envelope["role"], envelope["mfa_verified"],
                      envelope["email_verified"], key)
    except (ValueError, TypeError, UnicodeError, ApiError):
        return _error(400, "Invalid request")
    if ctx.role not in op.roles:
        return _error(403, "Forbidden")
    if op.mfa and not ctx.mfa_verified:
        return _error(403, "Forbidden")
    if op.verified_email and not ctx.email_verified:
        return _error(403, "Verified email required")
    try:
        if op.budget and not throttle.allow(op.budget, ctx.actor_id):
            return _error(429, "Too many requests")
        result, secret = _run(op, ctx, envelope["data"])
        return _respond(result, secret)
    except ApiError as error:
        return _error(error.status, error.detail, error.code)
    except DatabaseError:
        logger.error("Business database unavailable")
        return _error(503, "Business service unavailable")


from . import ownership  # noqa: E402,F401  (registers the operations)
