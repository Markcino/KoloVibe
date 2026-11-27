"""Decision C slice 2a: Engagement erases one account's engagement data (docs/privacy/account-erasure-plan-PROPOSED.md).

Run once per erasure request, through the idempotent inbox, in one transaction with its confirmation event:
- deleted: the person's likes, follows, shares and watch sessions (public counts drop accordingly);
- retained, decision pending: qualified watches (Points evidence) and fraud holds (abuse records). Their retention is
  a policy decision (ADR-020), so they are reported as retained and the request stays open in Identity.
Nothing here reads another service's database; the confirmation carries category names and counts only.
"""
import uuid

from django.db import transaction

from .events import accept_once, record_event
from .models import CreatorFollow, FraudHold, QualifiedWatch, VideoLike, VideoShare, WatchSession

ERASURE_REQUESTED = "privacy.erasure_requested"
ERASURE_CONFIRMED = "privacy.erasure_confirmed"
EXPORT_REQUESTED = "privacy.export_requested"
EXPORT_DELIVERED = "privacy.export_delivered"
# Access export (mandate 3.3): the person's own engagement records, by video or creator id and time. Fraud holds are
# abuse-investigation records; whether a person may see them is an owner decision, so they are withheld by name.
EXPORT_ROW_LIMIT = 5000
EXPORT = {
    "likes": (VideoLike, ("video_id", "created_at")),
    "follows": (CreatorFollow, ("creator_id", "created_at")),
    "shares": (VideoShare, ("video_id", "created_at")),
    "watch_sessions": (WatchSession, ("video_id", "started_at", "last_sample_at", "position_ms", "duration_ms",
                                      "qualified_at")),
    "qualified_watches": (QualifiedWatch, ("video_id", "qualified_at", "duration_ms", "watched_ms")),
}
WITHHELD = {"fraud_holds": FraudHold}
DELETED = {"likes": VideoLike, "follows": CreatorFollow, "shares": VideoShare, "watch_sessions": WatchSession}
RETAINED = {"qualified_watches": QualifiedWatch, "fraud_holds": FraudHold}


def _request(payload):
    if (not isinstance(payload, dict) or set(payload) != {"request_id", "account_id", "service"}
            or payload["service"] != "engagement"):
        raise ValueError("Invalid privacy request")
    for key in ("request_id", "account_id"):
        if not isinstance(payload[key], str) or str(uuid.UUID(payload[key])) != payload[key]:
            raise ValueError("Invalid erasure request")
    return payload["request_id"], payload["account_id"]


def erase(event_id, payload):
    """Erase once and record the confirmation; a repeated delivery changes nothing and returns False."""
    request_id, account_id = _request(payload)
    with transaction.atomic():
        if not accept_once(event_id, ERASURE_REQUESTED):
            return False
        counts = {}
        for name, model in DELETED.items():
            counts[name], _ = model.objects.filter(account_id=account_id).delete()
        retained = [name for name, model in RETAINED.items() if model.objects.filter(account_id=account_id).exists()]
        record_event(ERASURE_CONFIRMED, {"request_id": request_id, "account_id": account_id, "service": "engagement",
                                         "counts": counts, "retained": retained})
        return True


def _plain(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    return value.isoformat() if hasattr(value, "isoformat") else value


def _rows(model, fields, account_id):
    rows = list(model.objects.filter(account_id=account_id).order_by("pk").values_list(*fields)[:EXPORT_ROW_LIMIT + 1])
    return ([{name: _plain(value) for name, value in zip(fields, row)} for row in rows[:EXPORT_ROW_LIMIT]],
            len(rows) > EXPORT_ROW_LIMIT)


def export(event_id, payload):
    """Assemble the person's engagement records once and deliver them to Identity; a repeat returns False."""
    request_id, account_id = _request(payload)
    with transaction.atomic():
        if not accept_once(event_id, EXPORT_REQUESTED):
            return False
        data, truncated = {}, []
        for name, (model, fields) in EXPORT.items():
            data[name], cut = _rows(model, fields, account_id)
            if cut:
                truncated.append(name)
        withheld = [name for name, model in WITHHELD.items() if model.objects.filter(account_id=account_id).exists()]
        record_event(EXPORT_DELIVERED, {"request_id": request_id, "account_id": account_id, "service": "engagement",
                                        "data": data, "withheld": withheld, "truncated": truncated})
        return True
