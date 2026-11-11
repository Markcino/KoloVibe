from django.db import connection
from .models import AuditDelivery, SecurityEvent

KINDS = {
    "account.registered", "account.verified", "account.verification_resent",
    "account.password_reset_requested", "account.password_reset", "account.password_changed",
    "account.profile_updated", "account.preferences_updated", "account.privacy_request_received",
    "login.failed", "login.throttled",
    "login.succeeded", "mfa.challenge", "mfa.failed", "mfa.enrolled",
    "mfa.succeeded", "mfa.recovery_used", "session.rotated", "session.replay",
    "session.revoked",
}


def record(kind, actor_id=None):
    if kind not in KINDS or not connection.in_atomic_block:
        raise RuntimeError("Security events require a known kind and owning transaction")
    event = SecurityEvent.objects.create(kind=kind, actor_id=actor_id)
    AuditDelivery.objects.create(event=event)
    return event
