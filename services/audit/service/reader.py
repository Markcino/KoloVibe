"""Read-only projection of immutable evidence; raw payload, actor and subject IDs are redacted."""
import hashlib
import json
from datetime import datetime
from uuid import UUID
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import SecurityEvent, AuditReadGrant
from .events import PRODUCER_KINDS


def evidence(actor, allowed):
    SecurityEvent.objects.create(actor_id=actor, kind="audit.read" if allowed else "audit.read_denied",
        occurred_at=timezone.now(), producer="audit", subject_type="account", subject_id=actor,
        payload_digest=hashlib.sha256((str(actor) + (":read" if allowed else ":denied")).encode()).hexdigest())


@require_POST
def read_events(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 2048:
            raise ValueError
        body = json.loads(request.body)
        if not isinstance(body, dict) or set(body) != {"actor_id", "role", "mfa_verified", "data"}:
            raise ValueError
        actor = UUID(body["actor_id"])
        if body["role"] not in {"moderator", "administrator"} or body["mfa_verified"] is not True:
            with transaction.atomic():
                evidence(actor, False)
            return JsonResponse({"detail": "Forbidden"}, status=403)
        data = body["data"]
        if not isinstance(data, dict) or set(data) - {"cursor", "kind", "producer", "since", "until"}:
            raise ValueError
        query = SecurityEvent.objects.all()
        if body["role"] == "moderator":
            query = query.filter(actor_id=actor)
        else:
            grants = AuditReadGrant.objects.filter(administrator_id=actor, active=True)
            if not grants.exists():
                with transaction.atomic():
                    evidence(actor, False)
                return JsonResponse({"detail": "Forbidden"}, status=403)
            query = query.filter(producer__in=grants.values("producer"))
        for field in ("producer", "kind"):
            if data.get(field):
                known = set(PRODUCER_KINDS) | {"audit"} if field == "producer" else set().union(*PRODUCER_KINDS.values()) | {"audit.read", "audit.read_denied", "audit.erasure_recovery_read"}
                if not isinstance(data[field], str) or data[field] not in known:
                    raise ValueError
                query = query.filter(**{field: data[field]})
        stamps = {}
        for field in ("since", "until"):
            if data.get(field):
                stamp = datetime.fromisoformat(data[field])
                if stamp.tzinfo is None:
                    raise ValueError
                stamps[field] = stamp
                query = query.filter(**{"occurred_at__gte" if field == "since" else "occurred_at__lte": stamp})
        if stamps.get("since", datetime.min.replace(tzinfo=timezone.now().tzinfo)) > stamps.get("until", datetime.max.replace(tzinfo=timezone.now().tzinfo)):
            raise ValueError
        cursor = data.get("cursor")
        if cursor is not None:
            if not isinstance(cursor, str) or str(UUID(cursor)) != cursor:
                raise ValueError
            last = query.filter(pk=cursor).first()
            if last is None:
                raise ValueError
            query = query.filter(Q(occurred_at__lt=last.occurred_at) | Q(occurred_at=last.occurred_at, id__lt=last.id))
        rows = list(query.order_by("-occurred_at", "-id")[:21])
        items = [{"id": str(row.id), "kind": row.kind, "occurred_at": row.occurred_at.isoformat(),
                  "producer": row.producer, "subject_type": row.subject_type} for row in rows[:20]]
        with transaction.atomic():
            evidence(actor, True)
        result = JsonResponse({"items": items, "next_cursor": items[-1]["id"] if len(rows) > 20 else None})
        result["Cache-Control"] = "private, no-store"
        return result
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    except DatabaseError:
        return JsonResponse({"detail": "Service unavailable"}, status=503)
