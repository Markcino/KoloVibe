from uuid import UUID

from django.http import JsonResponse
from django.db import transaction
from django.db.models import Count
from .security_audit import record
from .models import ModeratorAssignment, Report, Appeal
from .reviewer import denied


def operational_read(operation, actor, role, content):
    grants = ModeratorAssignment.objects.filter(moderator_id=actor, active=True)
    if role == "moderator" and not grants.exists():
        return denied(actor)
    with transaction.atomic():
        record("moderation.totals_read" if operation == "totals" else "moderation.fraud_scope_read", actor, "account", actor)
    videos = grants.filter(queue_scope="videos").values_list("target_id", flat=True)
    reports = Report.objects.all()
    appeals = Appeal.objects.all()
    if role == "moderator":
        reports = reports.filter(pk__in=grants.filter(queue_scope="reports").values("target_id"))
        appeals = appeals.filter(pk__in=grants.filter(queue_scope="appeals").values("target_id"))
    from .workflow import ContentUnavailable
    scope = None
    if role == "moderator":
        scope = set(videos[:1001])
        if operation == "fraud_scope":
            scope.update(reports.values_list("video_id", flat=True).distinct()[:1001])
            scope.update(appeals.values_list("removal__video_id", flat=True).distinct()[:1001])
        if len(scope) > 1000:
            raise ContentUnavailable
    if operation == "fraud_scope":
        return JsonResponse({"video_ids": sorted(map(str, scope)) if scope is not None else None})
    counts = content("totals", {"scope_ids": sorted(map(str, scope)) if scope is not None else None})
    if counts is None:
        raise ContentUnavailable
    if (not isinstance(counts, dict) or set(counts) != {"review", "published", "rejected", "removed"}
            or any(type(value) is not int or value < 0 for value in counts.values())):
        raise ContentUnavailable
    return JsonResponse({"videos": counts, "reports": {state: reports.filter(status=state).count()
        for state in ("open", "resolved", "dismissed")}, "appeals": {state: appeals.filter(status=state).count()
        for state in ("open", "denied", "restored")}})


SCOPES = {"videos", "reports", "appeals"}
MAX_ASSIGNEES = 100


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError
    return parsed


def assignments(operation, actor, data, content):
    """Administrator-only explicit grants. A grant names one moderator and one resource.

    Grants are idempotent: repeating the same state changes nothing and records no event.
    Administrators keep global supervision and are never given or denied a grant here.
    """
    if operation == "assignment_summary":
        return _summary(data["moderator_ids"])
    try:
        scope = data["scope"]
        if scope not in SCOPES:
            raise ValueError
        target = _uuid(data["target_id"])
        if operation == "assignment_set":
            moderator, active = _uuid(data["moderator_id"]), data["active"]
            if type(active) is not bool or moderator == actor:
                raise ValueError
    except (ValueError, TypeError, KeyError):
        return JsonResponse({"detail": "Invalid assignment request"}, status=400)
    if scope == "reports":
        exists = Report.objects.filter(pk=target).exists()
    elif scope == "appeals":
        exists = Appeal.objects.filter(pk=target).exists()
    else:
        exists = content("detail", {"video_id": str(target)}) is not None
    if not exists:
        return JsonResponse({"detail": "Resource unavailable"}, status=404)
    if operation == "assignment_set":
        result = {"scope": scope, "target_id": str(target), "moderator_id": str(moderator), "active": active}
        with transaction.atomic():
            grant = ModeratorAssignment.objects.select_for_update().filter(
                moderator_id=moderator, queue_scope=scope, target_id=target).first()
            if grant is None and active:
                ModeratorAssignment.objects.create(moderator_id=moderator, queue_scope=scope, target_id=target)
            elif grant is not None and grant.active != active:
                grant.active = active
                grant.save(update_fields=["active"])
            else:
                return JsonResponse(result)
            record("moderation.assignment_changed", actor, "account", moderator)
        return JsonResponse(result)
    rows = ModeratorAssignment.objects.filter(queue_scope=scope, target_id=target, active=True)
    return JsonResponse({"scope": scope, "target_id": str(target), "items": [
        {"moderator_id": str(row)} for row in rows.order_by("moderator_id").values_list("moderator_id", flat=True)[:MAX_ASSIGNEES]]})


MAX_SUMMARY = 50


def _summary(value):
    """Active grants per moderator, for workload visibility. Every requested moderator is answered."""
    try:
        if not isinstance(value, list) or not 1 <= len(value) <= MAX_SUMMARY:
            raise ValueError
        ids = [_uuid(item) for item in value]
        if len(set(ids)) != len(ids):
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"detail": "Invalid assignment request"}, status=400)
    counts = {moderator: dict.fromkeys(SCOPES, 0) for moderator in ids}
    for row in (ModeratorAssignment.objects.filter(moderator_id__in=ids, active=True)
                .values("moderator_id", "queue_scope").annotate(total=Count("id"))):
        counts[row["moderator_id"]][row["queue_scope"]] = row["total"]
    return JsonResponse({"items": [{"moderator_id": str(moderator), **counts[moderator]} for moderator in sorted(ids, key=str)]})
