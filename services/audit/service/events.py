import hashlib
import json
import logging
import uuid
from datetime import datetime

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import SecurityEvent

logger = logging.getLogger(__name__)
KINDS = {
    "account.registered", "account.verified", "account.verification_resent",
    "account.password_reset_requested", "account.password_reset", "account.password_changed",
    "account.profile_updated", "account.preferences_updated", "account.privacy_request_received",
    "account.reauthenticated", "account.reauthentication_failed", "account.reauthentication_throttled",
    "login.failed", "login.throttled",
    "login.succeeded", "mfa.challenge", "mfa.failed", "mfa.enrolled",
    "mfa.succeeded", "mfa.recovery_used", "session.rotated", "session.replay",
    "session.revoked", "session.listed",
}


@require_POST
def ingest(request):
    if getattr(request, "service_caller", None) != "identity":
        logger.warning("Rejected unauthorized security event publisher")
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if len(request.body) > 2048:
            raise ValueError("Oversized event")
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"id", "actor_id", "kind", "occurred_at"}:
            raise ValueError("Invalid event")
        if (not all(isinstance(data[key], str) for key in ("id", "kind", "occurred_at"))
                or (data["actor_id"] is not None and not isinstance(data["actor_id"], str))):
            raise ValueError("Invalid event types")
        event_id = uuid.UUID(data["id"])
        actor = uuid.UUID(data["actor_id"]) if data["actor_id"] is not None else None
        stamp = datetime.fromisoformat(data["occurred_at"])
        if stamp.tzinfo is None or data["kind"] not in KINDS:
            raise ValueError("Invalid event")
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    except (ValueError, TypeError, KeyError, UnicodeError):
        logger.warning("Rejected malformed security event")
        return JsonResponse({"detail": "Invalid event"}, status=400)
    with transaction.atomic():
        event, created = SecurityEvent.objects.get_or_create(
            id=event_id, defaults={"actor_id": actor, "kind": data["kind"],
                                  "occurred_at": stamp, "payload_digest": digest})
        if event.payload_digest != digest:
            logger.error("Security event identifier collision")
            return JsonResponse({"detail": "Event conflict"}, status=409)
    return JsonResponse({"status": "ok"}, status=201 if created else 200)
