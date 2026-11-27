"""Mandate 3.4 (PROPOSED contract): the erasure recovery source for Identity after a restore.

Audit has its own database and append-only storage, so it still holds what Identity recorded after an older Identity
backup was taken. Only Identity may read this, and only two facts: which accounts an approved deletion deactivated,
and which accounts an erasure completed for (`account.deactivated`, `account.privacy_erasure_completed`, both
recorded by Identity with the account as the actor). It answers account ids, kinds and times, nothing else, and every
read is itself recorded. Identity's `recover_erasures_from_audit` re-applies them, so a restore cannot bring an erased
or deactivated account back.
"""
import hashlib
import json
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import SecurityEvent

KINDS = ("account.deactivated", "account.privacy_erasure_completed")
PAGE = 500


def _evidence(count):
    SecurityEvent.objects.create(
        actor_id=None, kind="audit.erasure_recovery_read", occurred_at=timezone.now(), producer="audit",
        subject_type="service", payload_digest=hashlib.sha256(f"identity:{count}".encode()).hexdigest())


@require_POST
def erasure_recovery(request):
    if getattr(request, "service_caller", None) != "identity":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 256:
            raise ValueError
        body = json.loads(request.body)
        if not isinstance(body, dict) or set(body) - {"cursor"}:
            raise ValueError
        query = SecurityEvent.objects.filter(producer="identity", kind__in=KINDS, actor_id__isnull=False)
        cursor = body.get("cursor")
        if cursor is not None:
            if not isinstance(cursor, str) or str(UUID(cursor)) != cursor:
                raise ValueError
            last = query.filter(pk=cursor).first()
            if last is None:
                raise ValueError
            query = query.filter(Q(occurred_at__gt=last.occurred_at) | Q(occurred_at=last.occurred_at, id__gt=last.id))
        rows = list(query.order_by("occurred_at", "id")[:PAGE + 1])
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    items = [{"id": str(row.id), "account_id": str(row.actor_id), "kind": row.kind,
              "occurred_at": row.occurred_at.isoformat()} for row in rows[:PAGE]]
    with transaction.atomic():
        _evidence(len(items))
    result = JsonResponse({"items": items, "next_cursor": items[-1]["id"] if len(rows) > PAGE else None})
    result["Cache-Control"] = "private, no-store"
    return result
