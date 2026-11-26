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
    "account.legal_accepted", "account.marketing_consent_changed",
    "account.privacy_requests_listed", "account.privacy_review_started", "account.privacy_request_declined",
    "account.privacy_deletion_approved", "account.privacy_hold_placed", "account.privacy_hold_released",
    "account.privacy_review_denied", "account.deactivated",
    "login.failed", "login.throttled",
    "login.succeeded", "mfa.challenge", "mfa.failed", "mfa.enrolled",
    "mfa.succeeded", "mfa.recovery_used", "session.rotated", "session.replay",
    "session.revoked", "session.listed",
}

PRODUCER_KINDS = {
    "identity": KINDS,
    "moderation": {"moderation.report_created", "moderation.appeal_created", "moderation.decision_recorded",
                   "moderation.decision_applied", "moderation.decision_conflicted", "moderation.assignment_denied", "moderation.assignment_changed", "moderation.reviewer_read", "moderation.preview_read", "moderation.totals_read", "moderation.fraud_scope_read", "moderation.counter_notice_created", "moderation.copyright_status_read",
                   "moderation.rights_holder_verified", "moderation.rights_holder_revoked"},
    "creators": {"creator.invited", "creator.invitation_revoked", "creator.application_submitted", "creator.approved", "creator.rejected",
                 "creator.profile_updated", "creator.restricted", "creator.suspended", "creator.restored",
                 "creator.warned", "creator.restriction_appealed", "creator.restriction_appeal_decided"},
    "content": {"video.created", "video.updated", "video.upload_intent_created", "video.upload_completed",
                "video.processing_succeeded", "video.processing_failed", "video.deleted", "video.published",
                "video.unpublished", "video.moderated", "video.edit_submitted", "video.edit_withdrawn",
                "video.edit_approved", "video.edit_rejected"},
    "business": {"business.registered", "business.membership_granted", "business.membership_revoked",
                 "business.invitation_created", "business.invitation_redeemed", "business.invitation_revoked",
                 "business.registration_grant_changed", "business.reviewer_grant_changed",
                 "business.verification_submitted", "business.verification_responded",
                 "business.verification_claimed", "business.verification_decided",
                 "business.verification_queue_read", "business.verification_case_read",
                 "business.profile_edited", "business.profile_submitted", "business.profile_applied",
                 "business.profile_decided", "business.profile_queue_read", "business.profile_revision_read",
                 "business.hours_replaced", "business.category_changed",
                 "business.listing_published", "business.listing_unpublished", "business.inquiry_created",
                 "business.inquiry_closed", "business.inquiry_blocked", "business.inquiry_confirmed",
                 "business.review_created", "business.review_held", "business.review_edited",
                 "business.review_withdrawn", "business.review_invitation_created",
                 "business.review_invitation_revoked", "business.review_responded", "business.report_created",
                 "business.report_decided", "business.report_queue_read", "business.report_case_read"},
    "points": {"points.awarded", "points.withheld", "points.reversed", "points.adjusted", "points.review_read", "points.review_denied"},
}
SUBJECT_TYPES = {"account", "creator", "video", "report", "appeal", "moderation_action", "points_entry", "business"}



@require_POST
def ingest(request):
    producer = getattr(request, "service_caller", None)
    if producer not in PRODUCER_KINDS:
        logger.warning("Rejected unauthorized security event publisher")
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if len(request.body) > 2048:
            raise ValueError("Oversized event")
        data = json.loads(request.body)
        required = {"id", "actor_id", "kind", "occurred_at"}
        if not isinstance(data, dict) or not required <= set(data) or set(data) - required - {"subject_type", "subject_id"}:
            raise ValueError("Invalid event")
        if (not all(isinstance(data[key], str) for key in ("id", "kind", "occurred_at"))
                or (data["actor_id"] is not None and not isinstance(data["actor_id"], str))):
            raise ValueError("Invalid event types")
        event_id = uuid.UUID(data["id"])
        actor = uuid.UUID(data["actor_id"]) if data["actor_id"] is not None else None
        stamp = datetime.fromisoformat(data["occurred_at"])
        if stamp.tzinfo is None or data["kind"] not in PRODUCER_KINDS[producer]:
            raise ValueError("Invalid event")
        subject_type, raw_subject = data.get("subject_type"), data.get("subject_id")
        if (subject_type is None) != (raw_subject is None):
            raise ValueError("Subject fields must be paired")
        if subject_type is not None and (not isinstance(subject_type, str) or subject_type not in SUBJECT_TYPES
                                         or not isinstance(raw_subject, str)):
            raise ValueError("Invalid subject")
        subject_id = uuid.UUID(raw_subject) if raw_subject is not None else None
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    except (ValueError, TypeError, KeyError, UnicodeError):
        logger.warning("Rejected malformed security event")
        return JsonResponse({"detail": "Invalid event"}, status=400)
    with transaction.atomic():
        event, created = SecurityEvent.objects.get_or_create(
            id=event_id, defaults={"actor_id": actor, "kind": data["kind"],
                                  "occurred_at": stamp, "payload_digest": digest, "producer": producer,
                                  "subject_type": subject_type, "subject_id": subject_id})
        if event.payload_digest != digest or event.producer != producer:
            logger.error("Security event identifier collision")
            return JsonResponse({"detail": "Event conflict"}, status=409)
    return JsonResponse({"status": "ok"}, status=201 if created else 200)

