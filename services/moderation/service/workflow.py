"""DEC-005 policy and recoverable delivery of moderation decisions."""

import json
import re
import time
from urllib.error import HTTPError
from uuid import UUID, uuid5

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import OuterRef, Q, Subquery
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .internal_client import signed_internal_request
from .models import (Appeal, ModerationAction, Report, ModeratorAssignment, CopyrightNotice,
                     CopyrightStrike, CounterNotice)
from .security_audit import record as audit_record


REVIEWERS = {"moderator", "administrator"}
VIEWERS = {"viewer", "creator"}
REPORT_REASONS = {"spam", "harassment", "copyright", "harmful", "other"}
RIGHTS_STATUSES = {"not_recorded", "attested", "flagged", "muted", "hidden", "removed", "restored"}
DECISIONS = {
    "video_decision": {"publish", "reject", "remove"},
    "report_decision": {"dismiss", "remove"},
    "appeal_decision": {"deny", "restore"},
}
FIELDS = {
    "copyright_report": {"video_id", "work_reference", "details", "authority_attested", "key"},
    "counter_notice": {"video_id", "creator_id", "reason", "accuracy_attested", "key"},
    "copyright_status": {"creator_id"},
    "report": {"video_id", "reason", "details", "key"},
    "appeal": {"video_id", "creator_id", "reason"},
    "review_queue": {"cursor"}, "reports": {"cursor"}, "appeals": {"cursor"},
    "own_reports": {"cursor"}, "own_appeals": {"cursor"},
    "own_report": {"target_id"}, "own_appeal": {"target_id"},
    "video_detail": {"target_id"}, "report_detail": {"target_id"}, "appeal_detail": {"target_id"},
    "preview": {"preview_id"}, "totals": set(), "fraud_scope": set(),
    "assignment_list": {"scope", "target_id"}, "assignment_set": {"scope", "target_id", "moderator_id", "active"},
    "assignment_summary": {"moderator_ids"},
    "notice": {"video_id", "creator_id"}, "standing": {"creator_id"},
    "edit_queue": {"cursor"}, "edit_detail": {"target_id"},
    "edit_decision": {"target_id", "action", "reason", "key"},
    **{operation: {"target_id", "action", "reason", "key"} for operation in DECISIONS},
}


ASSIGNMENT_OPERATIONS = {"assignment_list", "assignment_set", "assignment_summary"}


class ContentUnavailable(Exception):
    pass


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _content(operation, payload):
    try:
        with signed_internal_request("content", f"/internal/videos/moderation/{operation}",
                                     method="POST", payload=json.dumps(payload).encode(), timeout=2) as response:
            raw = response.read(65537)
            if response.status != 200 or len(raw) > 65536:
                raise ValueError("Unexpected Content response")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Invalid Content response")
            if operation == "inspect":
                if (set(data) != {"creator_id", "state", "visibility", "revision"}
                        or type(data["revision"]) is not int or data["revision"] < 0):
                    raise ValueError("Invalid moderation snapshot")
                UUID(data["creator_id"])
            elif operation == "detail":
                if (set(data) != {"id", "title", "description", "state", "duration_seconds", "rights_status", "preview_available"}
                        or data["id"] != payload["video_id"] or type(data["preview_available"]) is not bool
                        or not isinstance(data["title"], str) or not 1 <= len(data["title"]) <= 160
                        or not isinstance(data["description"], str) or len(data["description"]) > 2000
                        or data["rights_status"] not in {"attested", "flagged", "claimed", "removed", "restored"}):
                    raise ValueError("Invalid reviewer metadata")
            elif operation in {"apply", "rights", "edit-apply"} and (set(data) != {"applied"} or data["applied"] is not True):
                raise ValueError("Invalid moderation receipt")
            elif operation in {"edits", "edit-detail"}:
                from .edit_review import valid_content
                if not valid_content(operation, data, payload):
                    raise ValueError("Invalid edit review answer")
            return data
    except HTTPError as error:
        error.close()
        if error.code in (404, 409):
            return None
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError):
        pass
    raise ContentUnavailable


def _key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value):
        raise ValueError("Invalid idempotency key")
    return value


def _text(value, minimum=10):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= 2000 or len(value) > 2000:
        raise ValueError("Invalid reason or details")
    return value.strip()


def _report_data(report, *, reviewer=False):
    data = {"id": str(report.id), "video_id": str(report.video_id), "status": report.status,
            "created_at": report.created_at.isoformat()}
    if reviewer:
        data.update(reason=report.reason, details=report.details)
    return data


def _appeal_data(appeal, *, reviewer=False):
    data = {"id": str(appeal.id), "video_id": str(appeal.removal.video_id), "status": appeal.status,
            "created_at": appeal.created_at.isoformat()}
    if reviewer:
        data["reason"] = appeal.reason
    return data


def _report(actor, data):
    video_id = UUID(data["video_id"])
    reason, details = data["reason"], _text(data["details"], minimum=0)
    if not isinstance(reason, str) or reason not in REPORT_REASONS:
        raise ValueError("Invalid report reason")
    report_id = uuid5(actor, "report:" + _key(data["key"]))
    report = Report.objects.filter(pk=report_id).first()
    if report is None:
        if Report.objects.filter(video_id=video_id, reporter_id=actor, status="open").exists():
            return JsonResponse({"detail": "An open report already exists", "code": "already_reported"}, status=409)
        snapshot = _content("inspect", {"video_id": str(video_id)})
        if snapshot is None or (snapshot["state"], snapshot["visibility"]) != ("published", "public"):
            return _error("Video not found", 404)
        try:
            with transaction.atomic():
                report, created = Report.objects.get_or_create(id=report_id, defaults={
                    "video_id": video_id, "reporter_id": actor, "reason": reason, "details": details,
                })
                if created:
                    audit_record("moderation.report_created", actor, "report", report.id)
                    if data.get("work_reference"):
                        CopyrightNotice.objects.create(report=report, work_reference=data["work_reference"])
        except IntegrityError:
            if Report.objects.filter(video_id=video_id, reporter_id=actor, status="open").exists():
                return JsonResponse({"detail": "An open report already exists", "code": "already_reported"}, status=409)
            raise
    else:
        created = False
    if (report.video_id, report.reason, report.details) != (video_id, reason, details):
        return _error("Idempotency key already used", 409)
    if data.get("work_reference"):
        notice = CopyrightNotice.objects.filter(report=report).first()
        if notice is None or notice.work_reference != data["work_reference"]:
            return _error("Idempotency key already used", 409)
    if reason == "copyright":
        # Durable report precedes remote delivery; a lost response is recoverable with the same key.
        applied = _content("rights", {"video_id": str(video_id), "command_id": str(report.id),
            "report_id": str(report.id), "event": "claim", "actor_id": str(actor),
            "reason": details or "Copyright allegation submitted for review"})
        if applied is None:
            raise ContentUnavailable
    return JsonResponse(_report_data(report), status=201 if created else 200)


def _appeal(actor, data, *, copyright_only=False):
    video_id, creator_id, reason = UUID(data["video_id"]), UUID(data["creator_id"]), _text(data["reason"])
    snapshot = _content("inspect", {"video_id": str(video_id)})
    if snapshot is None or UUID(snapshot["creator_id"]) != creator_id:
        return _error("Video not found", 404)
    if snapshot["state"] != "removed":
        return _error("Video has no current removal to appeal", 409)
    removal = ModerationAction.objects.filter(
        video_id=video_id, action="remove", status="applied", revision=snapshot["revision"] - 1,
    ).first()
    if removal is None:
        return _error("Video has no current removal to appeal", 409)
    if copyright_only and not removal.copyright:
        return _error("No copyright takedown to contest", 409)
    with transaction.atomic():
        appeal, created = Appeal.objects.get_or_create(removal=removal, defaults={"appellant_id": actor, "reason": reason})
        if created:
            audit_record("moderation.appeal_created", actor, "appeal", appeal.id)
    if appeal.appellant_id != actor or appeal.reason != reason:
        return _error("An appeal already exists for this removal", 409)
    return JsonResponse(_appeal_data(appeal), status=201 if created else 200)


def _assignment_ids(actor, scope):
    return ModeratorAssignment.objects.filter(moderator_id=actor, queue_scope=scope, active=True).values_list("target_id", flat=True)


def _denied(actor, target=None):
    with transaction.atomic():
        audit_record("moderation.assignment_denied", actor, "account", target or actor)
    return _error("Assigned resource required", 403)


def _queue(operation, cursor, actor, role, status=None):
    scope = {"review_queue": "videos", "reports": "reports", "appeals": "appeals"}[operation]
    statuses = {"videos": {"review", "published", "rejected", "removed"}, "reports": {"open", "resolved", "dismissed"}, "appeals": {"open", "denied", "restored"}}
    status = ("review" if scope == "videos" else "open") if status is None else status
    if not isinstance(status, str) or status not in statuses[scope]:
        raise ValueError("Unsupported status")
    ids = _assignment_ids(actor, scope) if role == "moderator" else None
    if ids is not None and not ids.exists():
        return _denied(actor)
    if cursor is not None:
        cursor = str(UUID(cursor))
    if operation == "review_queue":
        data = {"cursor": cursor, **({"status": status} if status != "review" else {})}
        if ids is not None:
            bounded = list(ids[:1001])
            if len(bounded) > 1000:
                raise ContentUnavailable
            data["scope_ids"] = [str(item) for item in bounded]
        page = _content("queue", data)
        if page is None:
            raise ContentUnavailable
        return JsonResponse(page)
    query = (Report.objects.filter(status=status) if operation == "reports"
             else Appeal.objects.select_related("removal").filter(status=status))
    if ids is not None:
        query = query.filter(pk__in=ids)
    if cursor is not None:
        query = query.filter(id__gt=cursor)
    rows = list(query.order_by("id")[:21])
    render = _report_data if operation == "reports" else _appeal_data
    items = [render(row, reviewer=True) for row in rows[:20]]
    return JsonResponse({"items": items, "next_cursor": items[-1]["id"] if len(rows) > 20 else None})


def _own_records(operation, actor, data):
    is_report = operation in ("own_reports", "own_report")
    query = (Report.objects.filter(reporter_id=actor) if is_report else
             Appeal.objects.select_related("removal").filter(appellant_id=actor))
    render = _report_data if is_report else _appeal_data
    if operation in ("own_report", "own_appeal"):
        record = query.filter(pk=UUID(data["target_id"])).first()
        return JsonResponse(render(record, reviewer=True)) if record else _error("Record not found", 404)
    cursor = data["cursor"]
    if cursor is not None:
        query = query.filter(id__gt=UUID(cursor))
    rows = list(query.order_by("id")[:21])
    items = [render(row, reviewer=True) for row in rows[:20]]
    return JsonResponse({"items": items, "next_cursor": items[-1]["id"] if len(rows) > 20 else None})


def _grant(actor, operation, target):
    scope = {"video_decision": "videos", "report_decision": "reports", "appeal_decision": "appeals"}[operation]
    return ModeratorAssignment.objects.select_for_update().filter(
        moderator_id=actor, queue_scope=scope, target_id=target, active=True).first()


def _reserve(operation, actor, data, role):
    target, action, reason = UUID(data["target_id"]), data["action"], _text(data["reason"])
    if not isinstance(action, str) or action not in DECISIONS[operation]:
        raise ValueError("Invalid decision action")
    reason_code = data.get("reason_code", "REVIEWED_" + action.upper())
    if not isinstance(reason_code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", reason_code):
        raise ValueError("Invalid reason code")
    action_id = uuid5(actor, "decision:" + _key(data["key"]))
    with transaction.atomic():
        if role == "moderator" and _grant(actor, operation, target) is None:
            return _denied(actor)
        existing = ModerationAction.objects.select_for_update().filter(pk=action_id).first()
        if existing:
            recorded_target = existing.report_id or existing.appeal_id or existing.video_id
            recorded_operation = ("report_decision" if existing.report_id else
                                  "appeal_decision" if existing.appeal_id else "video_decision")
            if (recorded_operation, recorded_target, existing.action, existing.reason) != (operation, target, action, reason) or (existing.reason_code != reason_code and not (existing.reason_code is None and "reason_code" not in data)):
                return _error("Idempotency key already used", 409)
            return existing
        report = appeal = None
        if operation == "report_decision":
            report = Report.objects.select_for_update().filter(pk=target).first()
            if report is None:
                return _error("Report not found", 404)
            if report.status != "open":
                return _error("Report is already closed", 409)
            video_id = report.video_id
        elif operation == "appeal_decision":
            appeal = Appeal.objects.select_for_update().filter(pk=target).first()
            if appeal is None:
                return _error("Appeal not found", 404)
            if actor in (appeal.removal.reviewer_id, appeal.appellant_id):
                return _error("Independent appeal reviewer required", 403)
            if appeal.status != "open":
                return _error("Appeal is already closed", 409)
            video_id = appeal.removal.video_id
        else:
            video_id = target
        revision = creator_id = None
        if action not in ("dismiss", "deny"):
            snapshot = _content("inspect", {"video_id": str(video_id)})
            if snapshot is None:
                return _error("Video not found", 404)
            revision = snapshot["revision"]
            creator_id = UUID(snapshot["creator_id"])
            if appeal and (snapshot["state"] != "removed" or revision != appeal.removal.revision + 1):
                return _error("Video no longer matches the appealed removal", 409)
        record, created = ModerationAction.objects.get_or_create(pk=action_id, defaults={
            "video_id": video_id, "reviewer_id": actor, "action": action, "reason": reason,
            "revision": revision, "report": report, "appeal": appeal,
            "creator_id": creator_id, "reason_code": reason_code, "owner_lookup_completed": creator_id is not None,
            "copyright": bool(report and report.reason == "copyright" or appeal and appeal.removal.copyright
                              or reason_code == "COPYRIGHT_TAKEDOWN"),
        })
        if not created and ((record.video_id, record.action, record.reason, record.report_id, record.appeal_id) != (
            video_id, action, reason, report.id if report else None, appeal.id if appeal else None,
        ) or record.reason_code != reason_code):
            return _error("Idempotency key already used", 409)
        if created:
            audit_record("moderation.decision_recorded", actor, "moderation_action", record.id)
    return record


def _decide(operation, actor, data, role):
    record = _reserve(operation, actor, data, role)
    if isinstance(record, JsonResponse):
        return record
    if role == "moderator":
        with transaction.atomic():
            if _grant(actor, operation, UUID(data["target_id"])) is None:
                return _denied(actor)
            return _complete(record, actor)
    return _complete(record, actor)


def _complete(record, actor):
    if record.status == "pending":
        applied = record.action in ("dismiss", "deny")
        if record.action == "dismiss" and record.copyright:
            applied = _content("rights", {"video_id": str(record.video_id), "command_id": str(record.id),
                "report_id": str(record.report_id), "event": "dismiss", "actor_id": str(actor), "reason": record.reason}) is not None
        if not applied and record.action not in {"dismiss", "deny"}:
            applied = _content("apply", {
                "video_id": str(record.video_id), "action_id": str(record.id),
                "action": record.action, "revision": record.revision,
                **({"copyright": True, "actor_id": str(actor), "reason": record.reason,
                    "report_id": str(record.report_id or record.appeal.removal.report_id) if record.report_id or record.appeal_id and record.appeal.removal.report_id else None} if record.copyright else {}),
            }) is not None
        with transaction.atomic():
            record = ModerationAction.objects.select_for_update().get(pk=record.id)
            if record.status == "pending":
                record.status = "applied" if applied else "conflict"
                record.finished_at = timezone.now()
                record.save(update_fields=["status", "finished_at"])
                audit_record("moderation.decision_applied" if applied else "moderation.decision_conflicted",
                                    actor, "moderation_action", record.id)
                if applied and record.report_id:
                    Report.objects.filter(pk=record.report_id).update(
                        status="dismissed" if record.action == "dismiss" else "resolved",
                    )
                if applied and record.appeal_id:
                    Appeal.objects.filter(pk=record.appeal_id).update(
                        status="denied" if record.action == "deny" else "restored",
                    )
                if applied and record.copyright and record.action == "remove":
                    CopyrightStrike.objects.get_or_create(removal=record, defaults={"creator_id": record.creator_id})
                if applied and record.copyright and record.action == "restore" and record.appeal_id:
                    CopyrightStrike.objects.filter(removal_id=record.appeal.removal_id, reversed_by__isnull=True).update(reversed_by=record)
    if record.status != "applied":
        return _error("Video state changed before decision was applied", 409)
    return JsonResponse({"id": str(record.id), "video_id": str(record.video_id),
                         "action": record.action, "status": record.status})


VIDEO_ACTIONS = {"reject", "remove", "restrict", "restore", "publish"}


def _latest(video_id):
    return ModerationAction.objects.filter(video_id=video_id, status="applied", action__in=VIDEO_ACTIONS).order_by(
        "-finished_at", "-created_at", "-id").first()


def _notice_data(actor, video_id, action, snapshot=None):
    appeal = Appeal.objects.filter(removal=action, appellant_id=actor).first() if action else None
    decision = {"reject": "rejected", "remove": "removed", "restrict": "restricted", "restore": "restored"}.get(
        action.action if action else None, "none")
    return {"video_id": str(video_id), "decision": decision,
            "reason_code": action.reason_code if action and decision != "none" else None,
            "decided_at": (action.finished_at or action.created_at).isoformat() if action else None,
            "appealable": bool(action and action.action == "remove" and appeal is None and not Appeal.objects.filter(removal=action).exists() and snapshot
                               and action.revision is not None and snapshot["state"] == "removed"
                               and snapshot["revision"] == action.revision + 1),
            "appeal": _appeal_data(appeal, reviewer=True) if appeal else None}


def _notice(actor, data):
    video, creator = UUID(data["video_id"]), UUID(data["creator_id"])
    snapshot = _content("inspect", {"video_id": str(video)})
    if snapshot is None or UUID(snapshot["creator_id"]) != creator:
        return _error("Video not found", 404)
    return JsonResponse(_notice_data(actor, video, _latest(video), snapshot))


def _standing(actor, data):
    if data["creator_id"] is None:
        return JsonResponse({"notices": []})
    creator = UUID(data["creator_id"])
    deadline = time.monotonic() + 8
    def inspect(video_id):
        if time.monotonic() >= deadline:
            raise ContentUnavailable
        return _content("inspect", {"video_id": str(video_id)})
    latest = ModerationAction.objects.filter(video_id=OuterRef("video_id"), status="applied",
              action__in=VIDEO_ACTIONS).order_by("-finished_at", "-created_at", "-id").values("id")[:1]
    actions = ModerationAction.objects.filter(status="applied", id=Subquery(latest)).exclude(action="publish")
    # Older actions predate attribution. Verify their current owner through Content
    # rather than inventing ownership or exposing another creator's notices.
    legacy = list(actions.filter(creator_id__isnull=True, owner_lookup_completed=False).order_by("-created_at", "-id")[:21])
    if len(legacy) > 20:
        raise ContentUnavailable  # bounded; deployers must backfill legacy ownership
    legacy_owned = []
    for action in legacy:
        snapshot = inspect(action.video_id)
        if snapshot is not None and UUID(snapshot["creator_id"]) == creator:
            legacy_owned.append(action.id)
    rows = list(actions.filter(Q(creator_id=creator) | Q(id__in=legacy_owned)).order_by(
        "-finished_at", "-created_at", "-id")[:20])
    notices = []
    for action in rows:
        if action.action == "publish":
            continue
        snapshot = inspect(action.video_id)
        if snapshot is not None and UUID(snapshot["creator_id"]) == creator:
            notices.append(_notice_data(actor, action.video_id, action, snapshot))
    if time.monotonic() > deadline:
        raise ContentUnavailable
    return JsonResponse({"notices": notices})


@require_POST
def moderation_workflow(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return _error("Forbidden", 403)
    try:
        if request.GET or len(request.body) > 16384:
            raise ValueError("Request too large")
        envelope = json.loads(request.body)
        if not isinstance(envelope, dict) or not {"actor_id", "role", "data"} <= set(envelope) or set(envelope) - {"actor_id", "role", "data", "mfa_verified"}:
            raise ValueError("Invalid moderation envelope")
        actor, role, data = UUID(envelope["actor_id"]), envelope["role"], envelope["data"]
        expected = FIELDS.get(operation)
        if (not isinstance(role, str) or expected is None or not isinstance(data, dict)
                or not expected <= set(data) or set(data) - expected - ({"reason_code"} if operation in DECISIONS or operation == "edit_decision" else {"status"} if operation in {"review_queue", "reports", "appeals"} else set())):
            raise ValueError("Invalid moderation operation")
        allowed = ({"creator"} if operation in {"notice", "copyright_status", "counter_notice"} else VIEWERS | REVIEWERS if operation == "standing" else VIEWERS if operation in ("appeal", "own_appeals", "own_appeal") else
                   VIEWERS | REVIEWERS if operation in ("report", "copyright_report", "own_reports", "own_report") else REVIEWERS)
        if operation in ASSIGNMENT_OPERATIONS:
            allowed = {"administrator"}
        if role not in allowed:
            return _error("Forbidden", 403)
        if operation in ASSIGNMENT_OPERATIONS:
            if envelope.get("mfa_verified") is not True:
                return _error("MFA-verified reviewer session required", 403)
            from .operations import assignments
            return assignments(operation, actor, data, _content)
        if operation in DECISIONS or operation in {"review_queue", "reports", "appeals", "video_detail", "report_detail", "appeal_detail", "preview", "totals", "fraud_scope", "edit_queue", "edit_detail", "edit_decision"}:
            if envelope.get("mfa_verified") is not True:
                return _error("MFA-verified reviewer session required", 403)
        if operation in {"edit_queue", "edit_detail", "edit_decision"}:
            from . import edit_review
            handler = {"edit_queue": edit_review.queue, "edit_detail": edit_review.detail,
                       "edit_decision": edit_review.decide}[operation]
            return handler(actor, role, data, _content)
        if operation in {"totals", "fraud_scope"}:
            from .operations import operational_read
            return operational_read(operation, actor, role, _content)
        if operation in {"video_detail", "report_detail", "appeal_detail", "preview"}:
            from . import reviewer
            if operation == "preview":
                return reviewer.preview(actor, role, data)
            return reviewer.detail(operation, actor, role, data, _content)
        if operation == "notice":
            return _notice(actor, data)
        if operation == "standing":
            return _standing(actor, data)
        if operation == "report":
            return _report(actor, data)
        if operation in {"copyright_report", "counter_notice", "copyright_status"}:
            from .copyright import dispatch
            return dispatch(operation, actor, data)
        if operation == "appeal":
            return _appeal(actor, data)
        if operation.startswith("own_"):
            return _own_records(operation, actor, data)
        if operation in DECISIONS:
            return _decide(operation, actor, data, role=role)
        return _queue(operation, data["cursor"], actor, role, data.get("status"))
    except (ValueError, TypeError, AttributeError, KeyError):
        return _error("Invalid moderation request", 400)
    except IntegrityError:
        return _error("Another decision is pending or a record already exists", 409)
    except (ContentUnavailable, DatabaseError):
        return _error("Moderation temporarily unavailable", 503)
