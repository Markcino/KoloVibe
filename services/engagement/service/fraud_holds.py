import json
from uuid import UUID
from django.db import DatabaseError
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import FraudHold


@require_POST
def read_holds(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 48000:
            raise ValueError
        body = json.loads(request.body)
        if set(body) != {"actor_id", "role", "mfa_verified", "data"}:
            raise ValueError
        UUID(body["actor_id"])
        if body["role"] not in {"moderator", "administrator"} or body["mfa_verified"] is not True:
            return JsonResponse({"detail": "Forbidden"}, status=403)
        data = body["data"]
        if set(data) != {"video_ids", "cursor"}:
            raise ValueError
        scope = data["video_ids"]
        if body["role"] == "moderator" and (not isinstance(scope, list) or len(scope) > 1000):
            raise ValueError
        if body["role"] == "administrator" and scope is not None:
            raise ValueError
        query = FraudHold.objects.filter(active=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        if scope is not None:
            query = query.filter(video_id__in=[UUID(item) for item in scope])
        total = query.count()
        if data["cursor"] is not None:
            query = query.filter(id__gt=UUID(data["cursor"]))
        rows = list(query.order_by("id")[:21])
        items = [{"id": str(row.id), "video_id": str(row.video_id), "reason_code": row.reason_code,
                  "created_at": row.created_at.isoformat()} for row in rows[:20]]
        return JsonResponse({"total": total, "items": items, "next_cursor": items[-1]["id"] if len(rows) > 20 else None})
    except (ValueError, TypeError, AttributeError, KeyError):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    except DatabaseError:
        return JsonResponse({"detail": "Service unavailable"}, status=503)
