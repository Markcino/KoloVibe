"""Administrative read projection of the immutable non-cash ledger; no execution path."""
import json
from datetime import datetime
from uuid import UUID
from django.db import DatabaseError, transaction
from django.db.models import Sum, Exists, OuterRef
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import PointsEntry
from .security_audit import record

STATUSES = {"all": None, "awards": "AWARD", "reversals": "REVERSAL", "adjustments": "ADJUSTMENT"}


@require_POST
def review(request, operation):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 2048:
            raise ValueError
        body = json.loads(request.body)
        if not isinstance(body, dict) or set(body) != {"actor_id", "role", "mfa_verified", "data"}:
            raise ValueError
        actor = UUID(body["actor_id"])
        if body["role"] != "administrator" or body["mfa_verified"] is not True:
            with transaction.atomic():
                record("points.review_denied", actor, actor_id=actor, subject_type="account")
            return JsonResponse({"detail": "Forbidden"}, status=403)
        data = body["data"]
        if operation not in {"balances", "account"}:
            return JsonResponse({"detail": "Not found"}, status=404)
        allowed = {"cursor", "as_of"} | ({"account_id", "status"} if operation == "account" else set())
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError
        cursor = data.get("cursor")
        if cursor is not None and (not isinstance(cursor, str) or str(UUID(cursor)) != cursor):
            raise ValueError
        as_of = datetime.fromisoformat(data["as_of"]) if data.get("as_of") else timezone.now()
        if as_of.tzinfo is None or as_of > timezone.now():
            raise ValueError
        subject = UUID(data["account_id"]) if operation == "account" else actor
        with transaction.atomic():
            record("points.review_read", subject, actor_id=actor, subject_type="account")
        ledger = PointsEntry.objects.filter(created_at__lte=as_of)
        if operation == "balances":
            query = ledger.values("creator_user_id").annotate(balance=Sum("delta"))
            if cursor:
                query = query.filter(creator_user_id__gt=UUID(cursor))
            rows = list(query.order_by("creator_user_id")[:21])
            items = [{"account_id": str(row["creator_user_id"]), "balance": row["balance"], "currency": "POINTS"} for row in rows[:20]]
            payload = {"items": items, "next_cursor": items[-1]["account_id"] if len(rows) > 20 else None, "as_of": as_of.isoformat()}
            subject = actor
        else:
            account = UUID(data["account_id"])
            entries = ledger.filter(creator_user_id=account)
            if not entries.exists():
                return JsonResponse({"detail": "Resource unavailable"}, status=404)
            balance = entries.aggregate(balance=Sum("delta", default=0))["balance"]
            status = data.get("status", "all")
            if not isinstance(status, str) or status not in STATUSES:
                raise ValueError
            if STATUSES[status]:
                entries = entries.filter(entry_type=STATUSES[status])
            if cursor:
                if not entries.filter(pk=cursor).exists():
                    raise ValueError
                entries = entries.filter(entry_id__gt=UUID(cursor))
            entries = entries.annotate(is_reversed=Exists(ledger.filter(reversal_of=OuterRef("entry_id"), creator_user_id=account)))
            rows = list(entries.order_by("entry_id")[:21])
            items = [{"id": str(row.entry_id), "amount": row.delta, "kind": row.entry_type.lower(),
                "rule_version": row.rule_version, "reason_code": row.reason_code, "created_at": row.created_at.isoformat(),
                "reversal_review_state": "reversed" if row.is_reversed else "not_reversed" if row.entry_type == "AWARD" else "reversal" if row.entry_type == "REVERSAL" else "not_applicable"}
                for row in rows[:20]]
            payload = {"account_id": str(account), "balance": balance, "currency": "POINTS", "items": items,
                       "next_cursor": items[-1]["id"] if len(rows) > 20 else None, "as_of": as_of.isoformat()}
            subject = account
        result = JsonResponse(payload)
        result["Cache-Control"] = "private, no-store"
        return result
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
        return JsonResponse({"detail": "Invalid query"}, status=400)
    except DatabaseError:
        return JsonResponse({"detail": "Points service unavailable"}, status=503)
