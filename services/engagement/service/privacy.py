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
DELETED = {"likes": VideoLike, "follows": CreatorFollow, "shares": VideoShare, "watch_sessions": WatchSession}
RETAINED = {"qualified_watches": QualifiedWatch, "fraud_holds": FraudHold}


def _request(payload):
    if (not isinstance(payload, dict) or set(payload) != {"request_id", "account_id", "service"}
            or payload["service"] != "engagement"):
        raise ValueError("Invalid erasure request")
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
