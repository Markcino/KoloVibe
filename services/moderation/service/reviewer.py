"""Assignment-authorized reviewer reads; no object-store locations leave Content."""
import json
from datetime import timedelta
from uuid import UUID
from urllib.error import HTTPError
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from .internal_client import signed_internal_request
from .models import ModeratorAssignment, Report, Appeal, ModerationAction, ReviewerPreview
from .security_audit import record

MAX_PREVIEW = 50 * 1024 * 1024


def denied(actor):
    with transaction.atomic():
        record("moderation.assignment_denied", actor, "account", actor)
    return JsonResponse({"detail": "Resource unavailable"}, status=403)


def allowed(actor, role, scope, target):
    return role == "administrator" or ModeratorAssignment.objects.filter(
        moderator_id=actor, queue_scope=scope, target_id=target, active=True).exists()


def detail(operation, actor, role, data, content):
    scope = {"video_detail": "videos", "report_detail": "reports", "appeal_detail": "appeals"}[operation]
    target = UUID(data["target_id"])
    if not allowed(actor, role, scope, target):
        return denied(actor)
    with transaction.atomic():
        record("moderation.reviewer_read", actor, {"videos": "video", "reports": "report", "appeals": "appeal"}[scope], target)
    from .workflow import _report_data, _appeal_data
    if scope == "reports":
        item = Report.objects.filter(pk=target).first()
        if item is None:
            return JsonResponse({"detail": "Resource unavailable"}, status=404)
        video_id, receipt = item.video_id, _report_data(item, reviewer=True)
    elif scope == "appeals":
        item = Appeal.objects.select_related("removal").filter(pk=target).first()
        if item is None:
            return JsonResponse({"detail": "Resource unavailable"}, status=404)
        video_id, receipt = item.removal.video_id, _appeal_data(item, reviewer=True)
    else:
        video_id, receipt = target, None
    video = content("detail", {"video_id": str(video_id)})
    if video is None:
        return JsonResponse({"detail": "Resource unavailable"}, status=404)
    available = video.pop("preview_available")
    if receipt is None:
        receipt = {"id": str(target), "title": video["title"]}
    reports = Report.objects.filter(video_id=video_id)
    decisions = ModerationAction.objects.filter(video_id=video_id)
    if role == "moderator":
        reports = reports.filter(pk__in=ModeratorAssignment.objects.filter(
            moderator_id=actor, queue_scope="reports", active=True).values("target_id"))
        decisions = decisions.filter(reviewer_id=actor)
    report_rows = list(reports.order_by("-created_at", "-id")[:21])
    decision_rows = list(decisions.order_by("-created_at", "-id")[:21])
    preview = None
    if available:
        now = timezone.now()
        expired = ReviewerPreview.objects.filter(expires_at__lte=now).values_list("id", flat=True)[:100]
        ReviewerPreview.objects.filter(id__in=list(expired)).delete()
        lease = ReviewerPreview.objects.create(actor_id=actor, queue_scope=scope, target_id=target,
                                               video_id=video_id, expires_at=now + timedelta(seconds=60))
        preview = {"id": str(lease.id), "url": f"/api/v1/moderation/previews/{lease.id}",
                   "expires_at": lease.expires_at.isoformat()}
    return JsonResponse({"record": receipt, "video": video, "preview": preview,
        "reports": [_report_data(item, reviewer=True) for item in report_rows[:20]],
        "decisions": [{"id": str(item.id), "action": item.action, "reason": item.reason,
                       "status": item.status, "created_at": item.created_at.isoformat()} for item in decision_rows[:20]],
        "history_truncated": {"reports": len(report_rows) > 20, "decisions": len(decision_rows) > 20}})


def preview(actor, role, data):
    lease = ReviewerPreview.objects.filter(pk=UUID(data["preview_id"]), actor_id=actor,
                                           expires_at__gt=timezone.now()).first()
    if lease is None or not allowed(actor, role, lease.queue_scope, lease.target_id):
        return denied(actor)
    with transaction.atomic():
        record("moderation.preview_read", actor, "video", lease.video_id)
    try:
        with signed_internal_request("content", "/internal/videos/moderation/preview", method="POST", timeout=12,
             payload=json.dumps({"video_id": str(lease.video_id)}).encode()) as response:
            if response.status != 200 or response.headers.get("Content-Type") != "video/mp4":
                raise ValueError
            raw = response.read(MAX_PREVIEW + 1)
            if not 0 < len(raw) <= MAX_PREVIEW:
                raise ValueError
        result = HttpResponse(raw, content_type="video/mp4")
        result["Cache-Control"] = "private, no-store"
        return result
    except (OSError, ValueError, RuntimeError, HTTPError):
        return JsonResponse({"detail": "Preview unavailable"}, status=503)
