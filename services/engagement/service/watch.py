"""DEC-003 watch qualification, owned by Engagement."""

from datetime import timedelta
import json
from uuid import UUID, uuid4

from django.db import DatabaseError, models, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .events import QUALIFIED_VIEW, record_event
from .models import QualifiedWatch, WatchSession


SESSION_TTL = timedelta(seconds=90)
VIEW_WINDOW = timedelta(hours=24)
MAX_SAMPLE_GAP = timedelta(seconds=15)
PACING_TOLERANCE_MS = 250
MAX_POSITION_ADVANCE_MS = 5_000


def error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def start(data):
    now = timezone.now()
    defaults = {
        "creator_user_id": data["creator_user_id"], "duration_ms": data["duration_ms"],
        "revision": data["revision"], "started_at": now, "last_sample_at": now,
        "expires_at": now + SESSION_TTL,
    }
    with transaction.atomic():
        watch, created = WatchSession.objects.select_for_update().get_or_create(
            account_id=data["account_id"], video_id=data["video_id"], defaults=defaults,
        )
        if not created and watch.expires_at > now:
            if any(getattr(watch, key) != defaults[key] for key in ("creator_user_id", "duration_ms", "revision")):
                return error("Watch session unavailable", 409)
            if watch.invalidated:
                return error("Watch session unavailable", 409)
        elif not created:
            for name, value in defaults.items():
                setattr(watch, name, value)
            watch.session_id, watch.position_ms, watch.invalidated = uuid4(), 0, False
            watch.save(update_fields=[*defaults, "session_id", "position_ms", "invalidated"])
    return JsonResponse({"session_id": str(watch.session_id), "expires_at": watch.expires_at.isoformat()})


def progress(data):
    with transaction.atomic():
        watch = WatchSession.objects.select_for_update().filter(
            account_id=data["account_id"], video_id=data["video_id"], session_id=data["session_id"],
        ).first()
        if watch is None:
            return error("Watch session not found", 404)
        now = timezone.now()
        if (watch.invalidated or now >= watch.expires_at
                or any(getattr(watch, key) != data[key] for key in ("creator_user_id", "duration_ms", "revision"))):
            return error("Watch session unavailable", 409)
        already_qualified = watch.qualified_at is not None and watch.qualified_at > now - VIEW_WINDOW
        position = data["position_ms"]
        if already_qualified and position <= watch.position_ms:
            return JsonResponse({"qualified": True})
        if position < watch.position_ms:
            return JsonResponse({"qualified": already_qualified})
        interval = now - watch.last_sample_at
        elapsed_ms = (now - watch.started_at) // timedelta(milliseconds=1)
        interval_ms = interval // timedelta(milliseconds=1)
        if (position > watch.duration_ms or interval > MAX_SAMPLE_GAP
                or position - watch.position_ms > min(interval_ms + PACING_TOLERANCE_MS, MAX_POSITION_ADVANCE_MS)
                or position > elapsed_ms + PACING_TOLERANCE_MS):
            watch.invalidated = True
            watch.save(update_fields=["invalidated"])
            return error("Invalid playback progress", 409)
        if position > watch.position_ms:
            watch.position_ms, watch.last_sample_at = position, now
        # Round the approved 80% threshold up to a representable millisecond.
        threshold = min(30_000, (watch.duration_ms * 4 + 4) // 5)
        qualified = not already_qualified and min(position, elapsed_ms) >= threshold
        if qualified:
            watch.qualified_at = now
            QualifiedWatch.objects.create(
                session_id=watch.session_id, account_id=watch.account_id, video_id=watch.video_id,
                creator_user_id=watch.creator_user_id, qualified_at=now, duration_ms=watch.duration_ms,
                watched_ms=min(position, elapsed_ms),
            )
            record_event(QUALIFIED_VIEW, {
                "creator_user_id": str(watch.creator_user_id),
                "qualified_at": now.isoformat(),
            })
        elif already_qualified and watch.qualified_at >= watch.started_at:
            # Renewal inside the 24-hour dedupe window must not turn a replay
            # into another play or overwrite the original session's watch time.
            QualifiedWatch.objects.filter(
                session_id=watch.session_id, account_id=watch.account_id, video_id=watch.video_id,
                qualified_at=watch.qualified_at,
            ).filter(models.Q(watched_ms__isnull=True) | models.Q(watched_ms__lt=min(position, elapsed_ms))).update(
                watched_ms=min(position, elapsed_ms))
        watch.save(update_fields=["position_ms", "last_sample_at", "qualified_at"])
    return JsonResponse({"qualified": already_qualified or qualified})


@require_POST
def watch_api(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return error("Forbidden", 403)
    if operation not in ("start", "progress"):
        return error("Not found", 404)
    fields = {"account_id", "video_id", "creator_user_id", "duration_ms", "revision"}
    if operation == "progress":
        fields |= {"session_id", "position_ms"}
    try:
        if request.GET or len(request.body) > 1024:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError
        for field in fields & {"account_id", "video_id", "creator_user_id", "session_id"}:
            data[field] = UUID(data[field])
        if (type(data["duration_ms"]) is not int or not 1 <= data["duration_ms"] <= 300_000
                or type(data["revision"]) is not int or not 0 <= data["revision"] <= 2_147_483_647
                or operation == "progress" and (type(data["position_ms"]) is not int
                                                 or not 0 <= data["position_ms"] <= 300_000)):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        return error("Invalid watch request", 400)
    if data["account_id"] == data["creator_user_id"]:
        return error("Self-views do not qualify", 403)
    try:
        return start(data) if operation == "start" else progress(data)
    except DatabaseError:
        return error("Engagement service unavailable", 503)
