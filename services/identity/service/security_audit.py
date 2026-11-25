from django.db import connection
from .models import AuditDelivery, SecurityEvent

KINDS = {
    "moderator.invitation_created", "moderator.invitation_listed", "moderator.invitation_revoked",
    "moderator.invitation_setup_started", "moderator.invitation_accepted",
    "moderator.invitation_denied", "moderator.invitation_failed", "moderator.invitation_throttled",
    "account.administrator_role_granted", "account.creator_candidate_looked_up",
    "account.creator_role_granted",
    "account.registered", "account.registration_attempt_existing", "account.verified", "account.verification_resent",
    "account.password_reset_code_failed", "account.password_reset_throttled", "account.verification_code_failed", "account.verification_throttled",
    "account.password_reset_requested", "account.password_reset", "account.password_changed",
    "account.profile_updated", "account.preferences_updated", "account.privacy_request_received",
    "account.reauthenticated", "account.reauthentication_failed", "account.reauthentication_throttled",
    "account.step_up_issued", "account.step_up_consumed", "account.step_up_rejected",
    "login.failed", "login.throttled",
    "login.succeeded", "mfa.challenge", "mfa.failed", "mfa.enrolled",
    "mfa.succeeded", "mfa.recovery_used", "session.rotated", "session.replay",
    "session.revoked", "session.listed",
}


def record(kind, actor_id=None):
    if kind not in KINDS or not connection.in_atomic_block:
        raise RuntimeError("Security events require a known kind and owning transaction")
    event = SecurityEvent.objects.create(kind=kind, actor_id=actor_id)
    AuditDelivery.objects.create(event=event)
    return event

