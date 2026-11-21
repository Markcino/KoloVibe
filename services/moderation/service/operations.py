from django.http import JsonResponse
from django.db import transaction
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
