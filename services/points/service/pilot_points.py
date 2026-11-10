"""Apply DEC-003 events once and serve the creator's append-only ledger."""

from datetime import UTC, datetime, timedelta
import json
from uuid import UUID

from django.db import DatabaseError, transaction
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .events import accept_once
from .models import DailyAwardCount, PointsEntry


QUALIFIED_VIEW = "dec003.qualified_view"
RULE_VERSION = "DEC-003-v1"
DAILY_CAP = 100
PAGE_SIZE = 20


def apply_qualified_view(event_id, payload):
    if not isinstance(payload, dict) or set(payload) != {"creator_user_id", "qualified_at"}:
        raise ValueError("Invalid qualified-view payload")
    try:
        event_id = UUID(str(event_id))
        account = UUID(payload["creator_user_id"])
        qualified_at = datetime.fromisoformat(payload["qualified_at"])
        if timezone.is_naive(qualified_at) or qualified_at > timezone.now() + timedelta(minutes=1):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid qualified-view payload") from None
    day = qualified_at.astimezone(UTC).date()
    with transaction.atomic():
        if not accept_once(event_id, QUALIFIED_VIEW):
            return False
        counter, _ = DailyAwardCount.objects.get_or_create(creator_user_id=account, day=day)
        updated = DailyAwardCount.objects.filter(pk=counter.pk, awards__lt=DAILY_CAP).update(awards=F("awards") + 1)
        if not updated:
            return False
        PointsEntry.objects.create(
            creator_user_id=account, source_decision_id=event_id, delta=1,
            entry_type=PointsEntry.Type.AWARD, rule_version=RULE_VERSION, reason_code="QUALIFIED_VIEW",
        )
    return True


def _history(entries, creator_id, cursor):
    if cursor is not None:
        last = entries.filter(pk=cursor).first()
        if last is None:
            return JsonResponse({"detail": "Invalid points cursor"}, status=400)
        entries = entries.filter(Q(created_at__lt=last.created_at) | Q(created_at=last.created_at, pk__lt=last.pk))
    page = list(entries.order_by("-created_at", "-pk")[:PAGE_SIZE + 1])
    return JsonResponse({
        "items": [{
            "id": str(item.pk), "creator_id": str(creator_id), "amount": item.delta,
            "kind": item.entry_type.lower(), "rule_version": item.rule_version,
            "created_at": item.created_at.isoformat(),
        } for item in page[:PAGE_SIZE]],
        "next_cursor": str(page[PAGE_SIZE - 1].pk) if len(page) > PAGE_SIZE else None,
    })


@require_POST
def points_read(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if operation not in ("balance", "entries"):
        return JsonResponse({"detail": "Not found"}, status=404)
    try:
        if request.GET or len(request.body) > 512:
            raise ValueError
        data = json.loads(request.body)
        fields = {"account_id", "creator_id"} | ({"cursor"} if operation == "entries" else set())
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError
        account_id, creator_id = UUID(data["account_id"]), UUID(data["creator_id"])
        cursor = UUID(data["cursor"]) if data.get("cursor") is not None else None
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"detail": "Invalid points query"}, status=400)
    entries = PointsEntry.objects.filter(creator_user_id=account_id)
    try:
        if operation == "entries":
            return _history(entries, creator_id, cursor)
        balance = entries.aggregate(total=Sum("delta", default=0))["total"]
        return JsonResponse({"creator_id": str(creator_id), "balance": balance, "currency": "POINTS",
                             "as_of": timezone.now().isoformat()})
    except DatabaseError:
        return JsonResponse({"detail": "Points service unavailable"}, status=503)
