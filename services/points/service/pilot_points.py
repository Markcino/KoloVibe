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
from .models import DailyAwardCount, PointsEntry, QualificationReceipt
from .security_audit import record as audit_record


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
    # Commit receipt before posting: a processing failure leaves an honest pending
    # record. The broker retry resumes it; inbox + ledger + terminal state are atomic.
    receipt, _ = QualificationReceipt.objects.get_or_create(id=event_id, defaults={
        "creator_user_id": account, "qualified_at": qualified_at,
    })
    if receipt.creator_user_id != account or receipt.qualified_at != qualified_at:
        raise ValueError("Qualified event identifier conflict")
    with transaction.atomic():
        receipt = QualificationReceipt.objects.select_for_update().get(pk=event_id)
        if receipt.status != "pending":
            return False
        if not accept_once(event_id, QUALIFIED_VIEW):
            # Old consumed events may predate receipts. Only a retained ledger row
            # proves posting; otherwise the old outcome is explicitly unknown.
            receipt.status = "posted" if PointsEntry.objects.filter(source_decision_id=event_id).exists() else "legacy"
            receipt.save(update_fields=["status"])
            return False
        counter, _ = DailyAwardCount.objects.get_or_create(creator_user_id=account, day=day)
        updated = DailyAwardCount.objects.filter(pk=counter.pk, awards__lt=DAILY_CAP).update(awards=F("awards") + 1)
        if not updated:
            receipt.status, receipt.reason_code = "withheld", "DAILY_CAP"
            receipt.save(update_fields=["status", "reason_code"])
            audit_record("points.withheld", event_id)
            return False
        PointsEntry.objects.create(
            entry_id=event_id, creator_user_id=account, source_decision_id=event_id, delta=1,
            entry_type=PointsEntry.Type.AWARD, rule_version=RULE_VERSION, reason_code="QUALIFIED_VIEW",
        )
        receipt.status = "posted"
        receipt.save(update_fields=["status"])
        audit_record("points.awarded", event_id)
    return True


STATUSES = {"all", "confirmed", "pending", "adjustments"}


def _entry(item, creator_id):
    receipt = isinstance(item, QualificationReceipt)
    return {
        "id": str(item.pk), "creator_id": str(creator_id),
        "amount": item.amount if receipt else item.delta,
        "kind": "award" if receipt else item.entry_type.lower(),
        "rule_version": RULE_VERSION if receipt else item.rule_version,
        "created_at": (item.received_at if receipt else item.created_at).isoformat(),
        "status": item.status if receipt else "confirmed" if item.entry_type == "AWARD" else "adjustments",
        "video_id": None if receipt or item.video_id is None else str(item.video_id),
    }


def _queries(account, status):
    ledger = PointsEntry.objects.filter(creator_user_id=account)
    receipts = QualificationReceipt.objects.filter(creator_user_id=account, status__in=["pending", "withheld"])
    if status == "confirmed":
        return ledger.filter(entry_type="AWARD"), receipts.none()
    if status == "pending":
        return ledger.none(), receipts.filter(status="pending")
    if status == "adjustments":
        return ledger.exclude(entry_type="AWARD"), receipts.none()
    return ledger, receipts


def _find(queries, ident):
    return next((row for query in queries if (row := query.filter(pk=ident).first()) is not None), None)


def _history(queries, creator_id, cursor):
    last = _find(queries, cursor) if cursor is not None else None
    if cursor is not None and last is None:
        return JsonResponse({"detail": "Invalid points cursor"}, status=400)
    rows = []
    for index, query in enumerate(queries):
        field = "created_at" if index == 0 else "received_at"
        if last is not None:
            stamp = last.received_at if isinstance(last, QualificationReceipt) else last.created_at
            query = query.filter(Q(**{field + "__lt": stamp}) | Q(**{field: stamp, "pk__lt": last.pk}))
        rows.extend(query.order_by("-" + field, "-pk")[:PAGE_SIZE + 1])
    rows.sort(key=lambda item: (item.received_at if isinstance(item, QualificationReceipt) else item.created_at, item.pk), reverse=True)
    return JsonResponse({"items": [_entry(row, creator_id) for row in rows[:PAGE_SIZE]],
                         "next_cursor": str(rows[PAGE_SIZE - 1].pk) if len(rows) > PAGE_SIZE else None})


@require_POST
def points_read(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if operation not in ("balance", "entries", "entry"):
        return JsonResponse({"detail": "Not found"}, status=404)
    try:
        if request.GET or len(request.body) > 512:
            raise ValueError
        data = json.loads(request.body)
        base = {"account_id", "creator_id"}
        required = base | ({"cursor"} if operation == "entries" else {"entry_id"} if operation == "entry" else set())
        if (not isinstance(data, dict) or not required <= set(data)
                or set(data) - required - ({"status"} if operation == "entries" else set())):
            raise ValueError
        account_id, creator_id = UUID(data["account_id"]), UUID(data["creator_id"])
        cursor = UUID(data["cursor"]) if data.get("cursor") is not None else None
        status = data.get("status", "all")
        if not isinstance(status, str) or status not in STATUSES:
            raise ValueError
        entry_id = UUID(data["entry_id"]) if operation == "entry" else None
    except (ValueError, TypeError, AttributeError, KeyError):
        return JsonResponse({"detail": "Invalid points query"}, status=400)
    try:
        queries = _queries(account_id, status)
        if operation == "entries":
            return _history(queries, creator_id, cursor)
        if operation == "entry":
            item = _find(queries, entry_id)
            return JsonResponse(_entry(item, creator_id)) if item else JsonResponse({"detail": "Not found"}, status=404)
        entries = queries[0]
        total = lambda qs, field: qs.aggregate(total=Sum(field, default=0))["total"]
        return JsonResponse({
            "creator_id": str(creator_id), "balance": total(entries, "delta"), "currency": "POINTS",
            "confirmed": total(entries.filter(entry_type="AWARD"), "delta"),
            "pending": total(queries[1].filter(status="pending"), "amount"),
            "withheld": total(queries[1].filter(status="withheld"), "amount"),
            "reversed": -total(entries.filter(entry_type="REVERSAL"), "delta"),
            "as_of": timezone.now().isoformat(),
        })
    except DatabaseError:
        return JsonResponse({"detail": "Points service unavailable"}, status=503)
