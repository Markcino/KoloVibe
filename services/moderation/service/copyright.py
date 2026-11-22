"""Copyright intake and counter-notices reuse scoped, independently reviewed appeals."""
from uuid import UUID, uuid5
from django.db import transaction
from django.http import JsonResponse
from .models import Appeal, CopyrightStrike, CounterNotice
from .security_audit import record


def dispatch(operation, actor, data):
    from .workflow import _appeal, _report, _key, _text, _error
    if operation == "copyright_status":
        creator = UUID(data["creator_id"])
        with transaction.atomic():
            record("moderation.copyright_status_read", actor, "creator", creator)
        return JsonResponse({"strike_count": CopyrightStrike.objects.filter(creator_id=creator, reversed_by__isnull=True).count()})
    if operation == "copyright_report":
        if data["authority_attested"] is not True:
            raise ValueError("Authority attestation required")
        reference = data["work_reference"]
        if not isinstance(reference, str) or not 1 <= len(reference.strip()) <= 500 or len(reference) > 500:
            raise ValueError("Work reference required")
        details = _text(data["details"])
        if len(details) > 1400:
            raise ValueError("Copyright details exceed intake limit")
        return _report(actor, {"video_id": data["video_id"], "reason": "copyright",
            "details": "Work reference: " + reference.strip() + "\n" + details,
            "work_reference": reference.strip(), "key": data["key"]})
    if data["accuracy_attested"] is not True:
        raise ValueError("Accuracy attestation required")
    key = uuid5(actor, "counter:" + _key(data["key"]))
    existing = CounterNotice.objects.select_related("appeal__removal").filter(request_id=key).first()
    if existing:
        if (existing.account_id != actor or str(existing.appeal.removal.video_id) != data["video_id"]
                or existing.appeal.removal.creator_id != UUID(data["creator_id"])
                or existing.appeal.reason != _text(data["reason"])):
            return _error("Idempotency key already used", 409)
        from .workflow import _appeal_data
        return JsonResponse(_appeal_data(existing.appeal))
    with transaction.atomic():
        # Existing owner lookup and current-removal checks remain authoritative.
        result = _appeal(actor, {name: data[name] for name in ("video_id", "creator_id", "reason")}, copyright_only=True)
        if result.status_code not in {200, 201}:
            return result
        import json
        appeal = Appeal.objects.select_related("removal").get(pk=json.loads(result.content)["id"])
        if not appeal.removal.copyright or appeal.status != "open":
            return _error("No open copyright takedown to contest", 409)
        notice, created = CounterNotice.objects.get_or_create(appeal=appeal, defaults={"account_id": actor, "request_id": key})
        if (notice.account_id, notice.request_id) != (actor, key):
            return _error("Counter-notice already submitted", 409)
        if created:
            record("moderation.counter_notice_created", actor, "appeal", appeal.id)
    return result
