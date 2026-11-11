"""DEC-005 policy and recoverable delivery of moderation decisions."""

import json
import re
from urllib.error import HTTPError
from uuid import UUID, uuid5

from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .internal_client import signed_internal_request
from .models import Appeal, ModerationAction, Report


REVIEWERS = {"moderator", "administrator"}
VIEWERS = {"viewer", "creator"}
REPORT_REASONS = {"spam", "harassment", "copyright", "harmful", "other"}
DECISIONS = {
    "video_decision": {"publish", "reject", "remove"},
    "report_decision": {"dismiss", "remove"},
    "appeal_decision": {"deny", "restore"},
}
FIELDS = {
    "report": {"video_id", "reason", "details", "key"},
    "appeal": {"video_id", "creator_id", "reason"},
    "review_queue": {"cursor"}, "reports": {"cursor"}, "appeals": {"cursor"},
    "own_reports": {"cursor"}, "own_appeals": {"cursor"},
    "own_report": {"target_id"}, "own_appeal": {"target_id"},
    **{operation: {"target_id", "action", "reason", "key"} for operation in DECISIONS},
}


class ContentUnavailable(Exception):
    pass


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _content(operation, payload):
    try:
        with signed_internal_request("content", f"/internal/videos/moderation/{operation}",
                                     method="POST", payload=json.dumps(payload).encode()) as response:
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
            elif operation == "apply" and (set(data) != {"applied"} or data["applied"] is not True):
                raise ValueError("Invalid moderation receipt")
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
        snapshot = _content("inspect", {"video_id": str(video_id)})
        if snapshot is None or (snapshot["state"], snapshot["visibility"]) != ("published", "public"):
            return _error("Video not found", 404)
        report, created = Report.objects.get_or_create(id=report_id, defaults={
            "video_id": video_id, "reporter_id": actor, "reason": reason, "details": details,
        })
    else:
        created = False
    if (report.video_id, report.reason, report.details) != (video_id, reason, details):
        return _error("Idempotency key already used", 409)
    return JsonResponse(_report_data(report), status=201 if created else 200)


def _appeal(actor, data):
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
    appeal, created = Appeal.objects.get_or_create(removal=removal, defaults={"appellant_id": actor, "reason": reason})
    if appeal.appellant_id != actor or appeal.reason != reason:
        return _error("An appeal already exists for this removal", 409)
    return JsonResponse(_appeal_data(appeal), status=201 if created else 200)


def _queue(operation, cursor):
    if cursor is not None:
        cursor = str(UUID(cursor))
    if operation == "review_queue":
        page = _content("queue", {"cursor": cursor})
        if page is None:
            raise ContentUnavailable
        return JsonResponse(page)
    query = (Report.objects.filter(status="open") if operation == "reports"
             else Appeal.objects.select_related("removal").filter(status="open"))
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


def _reserve(operation, actor, data):
    target, action, reason = UUID(data["target_id"]), data["action"], _text(data["reason"])
    if not isinstance(action, str) or action not in DECISIONS[operation]:
        raise ValueError("Invalid decision action")
    action_id = uuid5(actor, "decision:" + _key(data["key"]))
    with transaction.atomic():
        existing = ModerationAction.objects.select_for_update().filter(pk=action_id).first()
        if existing:
            recorded_target = existing.report_id or existing.appeal_id or existing.video_id
            recorded_operation = ("report_decision" if existing.report_id else
                                  "appeal_decision" if existing.appeal_id else "video_decision")
            if (recorded_operation, recorded_target, existing.action, existing.reason) != (operation, target, action, reason):
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
        revision = None
        if action not in ("dismiss", "deny"):
            snapshot = _content("inspect", {"video_id": str(video_id)})
            if snapshot is None:
                return _error("Video not found", 404)
            revision = snapshot["revision"]
            if appeal and (snapshot["state"] != "removed" or revision != appeal.removal.revision + 1):
                return _error("Video no longer matches the appealed removal", 409)
        record, created = ModerationAction.objects.get_or_create(pk=action_id, defaults={
            "video_id": video_id, "reviewer_id": actor, "action": action, "reason": reason,
            "revision": revision, "report": report, "appeal": appeal,
        })
        if not created and (record.video_id, record.action, record.reason, record.report_id, record.appeal_id) != (
            video_id, action, reason, report.id if report else None, appeal.id if appeal else None,
        ):
            return _error("Idempotency key already used", 409)
    return record


def _decide(operation, actor, data):
    record = _reserve(operation, actor, data)
    if isinstance(record, JsonResponse):
        return record
    if record.status == "pending":
        applied = record.action in ("dismiss", "deny")
        if not applied:
            applied = _content("apply", {
                "video_id": str(record.video_id), "action_id": str(record.id),
                "action": record.action, "revision": record.revision,
            }) is not None
        with transaction.atomic():
            record = ModerationAction.objects.select_for_update().get(pk=record.id)
            if record.status == "pending":
                record.status = "applied" if applied else "conflict"
                record.finished_at = timezone.now()
                record.save(update_fields=["status", "finished_at"])
                if applied and record.report_id:
                    Report.objects.filter(pk=record.report_id).update(
                        status="dismissed" if record.action == "dismiss" else "resolved",
                    )
                if applied and record.appeal_id:
                    Appeal.objects.filter(pk=record.appeal_id).update(
                        status="denied" if record.action == "deny" else "restored",
                    )
    if record.status != "applied":
        return _error("Video state changed before decision was applied", 409)
    return JsonResponse({"id": str(record.id), "video_id": str(record.video_id),
                         "action": record.action, "status": record.status})


@require_POST
def moderation_workflow(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return _error("Forbidden", 403)
    try:
        if len(request.body) > 16384:
            raise ValueError("Request too large")
        envelope = json.loads(request.body)
        if not isinstance(envelope, dict) or set(envelope) != {"actor_id", "role", "data"}:
            raise ValueError("Invalid moderation envelope")
        actor, role, data = UUID(envelope["actor_id"]), envelope["role"], envelope["data"]
        if not isinstance(role, str) or operation not in FIELDS or not isinstance(data, dict) or set(data) != FIELDS[operation]:
            raise ValueError("Invalid moderation operation")
        allowed = (VIEWERS if operation in ("appeal", "own_appeals", "own_appeal") else
                   VIEWERS | REVIEWERS if operation in ("report", "own_reports", "own_report") else REVIEWERS)
        if role not in allowed:
            return _error("Forbidden", 403)
        if operation == "report":
            return _report(actor, data)
        if operation == "appeal":
            return _appeal(actor, data)
        if operation.startswith("own_"):
            return _own_records(operation, actor, data)
        if operation in DECISIONS:
            return _decide(operation, actor, data)
        return _queue(operation, data["cursor"])
    except (ValueError, TypeError, AttributeError, KeyError):
        return _error("Invalid moderation request", 400)
    except IntegrityError:
        return _error("Another decision is pending or a record already exists", 409)
    except (ContentUnavailable, DatabaseError):
        return _error("Moderation temporarily unavailable", 503)
