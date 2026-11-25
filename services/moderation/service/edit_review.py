"""Decision A (RV2-01): reviewing held edits to published videos.

Content holds the proposed text; Moderation records who decided and why, then asks Content to apply it.
A moderator sees and decides only edits to videos assigned to them; administrators see all of them.
"""

import re
from uuid import UUID, uuid5

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import EditDecision, ModeratorAssignment
from .security_audit import record

ACTIONS = {"approve", "reject"}
MATERIAL = {"title", "description", "category", "tags"}
STATUSES = {"pending", "approved", "rejected", "superseded", "withdrawn"}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _assigned(actor, role, video_id):
    return role == "administrator" or ModeratorAssignment.objects.filter(
        moderator_id=actor, queue_scope="videos", target_id=video_id, active=True).exists()


def _denied(actor):
    with transaction.atomic():
        record("moderation.assignment_denied", actor, "account", actor)
    return _error("Assigned resource required", 403)


def valid_values(values):
    return (isinstance(values, dict) and set(values) == MATERIAL
            and isinstance(values["title"], str) and 1 <= len(values["title"]) <= 160
            and isinstance(values["description"], str) and len(values["description"]) <= 2000
            and (values["category"] is None or isinstance(values["category"], str) and len(values["category"]) <= 16)
            and isinstance(values["tags"], list) and len(values["tags"]) <= 5
            and all(isinstance(tag, str) and re.fullmatch(r"[a-z0-9_]{1,30}", tag) for tag in values["tags"]))


def valid_content(operation, data, payload):
    """The Content answers this module relies on, checked at the trust boundary."""
    if operation == "edits":
        items = data.get("items")
        return (set(data) == {"items", "next_cursor"} and isinstance(items, list) and len(items) <= 20
                and all(isinstance(item, dict) and set(item) == {"id", "video_id", "title", "submitted_at"}
                        and all(isinstance(value, str) for value in item.values()) for item in items)
                and (data["next_cursor"] is None or bool(items) and data["next_cursor"] == items[-1]["id"]))
    if operation == "edit-detail":
        return (set(data) == {"id", "video_id", "creator_id", "status", "submitted_at", "video_state", "live", "proposed"}
                and data["id"] == payload["revision_id"] and data["status"] in STATUSES
                and all(isinstance(data[name], str) for name in ("video_id", "creator_id", "submitted_at", "video_state"))
                and valid_values(data["live"]) and valid_values(data["proposed"])
                and str(UUID(data["video_id"])) == data["video_id"] and str(UUID(data["creator_id"])) == data["creator_id"])
    return False


def queue(actor, role, data, content):
    from .workflow import ContentUnavailable
    request = {"cursor": str(UUID(data["cursor"])) if data["cursor"] is not None else None}
    if role == "moderator":
        ids = list(ModeratorAssignment.objects.filter(moderator_id=actor, queue_scope="videos", active=True)
                   .values_list("target_id", flat=True)[:1001])
        if not ids:
            return _denied(actor)
        if len(ids) > 1000:
            raise ContentUnavailable
        request["scope_ids"] = [str(item) for item in ids]
    page = content("edits", request)
    if page is None:
        raise ContentUnavailable
    return JsonResponse(page)


def _revision(revision_id, content):
    """The held edit, or None when Content has no such live revision."""
    return content("edit-detail", {"revision_id": str(revision_id)})


def detail(actor, role, data, content):
    revision_id = UUID(data["target_id"])
    revision = _revision(revision_id, content)
    if revision is None:
        return _error("Edit not found", 404)
    video_id = UUID(revision["video_id"])
    if not _assigned(actor, role, video_id):
        return _denied(actor)
    with transaction.atomic():
        record("moderation.reviewer_read", actor, "video", video_id)
    decisions = EditDecision.objects.filter(revision_id=revision_id)
    if role == "moderator":
        decisions = decisions.filter(reviewer_id=actor)
    revision.pop("creator_id")
    return JsonResponse({"edit": revision, "decisions": [
        {"id": str(item.id), "action": item.action, "reason": item.reason, "status": item.status,
         "created_at": item.created_at.isoformat()} for item in decisions.order_by("-created_at", "-id")[:20]]})


def _key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value):
        raise ValueError("Invalid idempotency key")
    return value


def _text(value):
    if not isinstance(value, str) or not 10 <= len(value.strip()) <= 2000 or len(value) > 2000:
        raise ValueError("Invalid reason")
    return value.strip()


def decide(actor, role, data, content):
    revision_id, action, reason = UUID(data["target_id"]), data["action"], _text(data["reason"])
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError("Invalid decision action")
    reason_code = data.get("reason_code", "REVIEWED_EDIT_" + action.upper())
    if not isinstance(reason_code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", reason_code):
        raise ValueError("Invalid reason code")
    decision_id = uuid5(actor, "edit-decision:" + _key(data["key"]))
    existing = EditDecision.objects.filter(pk=decision_id).first()
    if existing is not None:
        if (existing.revision_id, existing.action, existing.reason, existing.reason_code) != (
                revision_id, action, reason, reason_code):
            return _error("Idempotency key already used", 409)
        decision = existing
    else:
        revision = _revision(revision_id, content)
        if revision is None:
            return _error("Edit not found", 404)
        video_id = UUID(revision["video_id"])
        if not _assigned(actor, role, video_id):
            return _denied(actor)
        if revision["status"] != "pending":
            return _error("Edit is no longer pending", 409)
        with transaction.atomic():
            if EditDecision.objects.select_for_update().filter(revision_id=revision_id).exclude(status="conflict").exists():
                return _error("Another decision is pending or a record already exists", 409)
            decision = EditDecision.objects.create(
                id=decision_id, revision_id=revision_id, video_id=video_id, creator_id=UUID(revision["creator_id"]),
                reviewer_id=actor, action=action, reason=reason, reason_code=reason_code)
            record("moderation.decision_recorded", actor, "moderation_action", decision.id)
    if role == "moderator" and not _assigned(actor, role, decision.video_id):
        return _denied(actor)
    if decision.status == "pending":
        applied = content("edit-apply", {"revision_id": str(decision.revision_id), "action_id": str(decision.id),
                                         "action": decision.action, "reason_code": decision.reason_code}) is not None
        with transaction.atomic():
            decision = EditDecision.objects.select_for_update().get(pk=decision.id)
            if decision.status == "pending":
                decision.status = "applied" if applied else "conflict"
                decision.finished_at = timezone.now()
                decision.save(update_fields=["status", "finished_at"])
                record("moderation.decision_applied" if applied else "moderation.decision_conflicted",
                       actor, "moderation_action", decision.id)
    if decision.status != "applied":
        return _error("Edit changed before the decision was applied", 409)
    return JsonResponse({"id": str(decision.id), "video_id": str(decision.video_id),
                         "action": decision.action, "status": decision.status})
