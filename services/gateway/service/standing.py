"""Compose live account/creator standing and private moderation notices."""
from datetime import datetime
import json
import re
from urllib.error import HTTPError
from uuid import UUID

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .accounts import _bearer, _invoke
from .creator_onboarding import authenticated_actor
from .internal_client import signed_internal_request


def identity_context(request):
    token = _bearer(request)
    if token is None:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    result = _invoke("/internal/auth/standing", {"access_token": token}, {200})
    if result.status_code != 200:
        return result
    try:
        data = json.loads(result.content)
        if (not isinstance(data, dict) or set(data) != {"account_id", "account_status", "mfa_verified", "email_verified"}
                or str(UUID(data["account_id"])) != data["account_id"] or data["account_status"] != "active"
                or type(data["mfa_verified"]) is not bool or type(data["email_verified"]) is not bool):
            raise ValueError
        return data
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({"detail": "Identity unavailable"}, status=503)


def valid_notice(item):
    if (not isinstance(item, dict) or set(item) != {"video_id", "decision", "reason_code", "decided_at", "appealable", "appeal"}
            or str(UUID(item["video_id"])) != item["video_id"]
            or item["decision"] not in {"none", "rejected", "removed", "restricted", "restored"}
            or type(item["appealable"]) is not bool
            or item["reason_code"] is not None and (not isinstance(item["reason_code"], str)
                or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", item["reason_code"]))
            or item["decided_at"] is not None and datetime.fromisoformat(item["decided_at"]).tzinfo is None
            or item["decision"] != "none" and item["decided_at"] is None):
        return False
    appeal = item["appeal"]
    if appeal is not None:
        if (not isinstance(appeal, dict) or set(appeal) != {"id", "video_id", "status", "created_at", "reason"}
                or str(UUID(appeal["id"])) != appeal["id"] or appeal["video_id"] != item["video_id"]
                or appeal["status"] not in {"open", "denied", "restored"}
                or not isinstance(appeal["reason"], str) or not 10 <= len(appeal["reason"]) <= 2000
                or datetime.fromisoformat(appeal["created_at"]).tzinfo is None):
            return False
    return not item["appealable"] or item["decision"] == "removed" and appeal is None


def _creator_standing(actor, role):
    try:
        with signed_internal_request("creators", "/internal/creators/onboarding/standing", method="POST", timeout=3,
             payload=json.dumps({"actor_id": actor, "role": role, "data": {}}).encode()) as response:
            raw = response.read(1025)
            data = json.loads(raw)
            if (response.status != 200 or len(raw) > 1024 or not isinstance(data, dict)
                    or set(data) != {"creator_id", "creator_status", "publishing_allowed"}
                    or type(data["publishing_allowed"]) is not bool):
                raise ValueError
            if data["creator_id"] is None:
                if data["creator_status"] is not None or data["publishing_allowed"]:
                    raise ValueError
            elif (str(UUID(data["creator_id"])) != data["creator_id"]
                  or data["creator_status"] not in {"pending", "active", "restricted", "suspended"}
                  or data["publishing_allowed"] and data["creator_status"] != "active"):
                raise ValueError
            return data
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RuntimeError):
        return JsonResponse({"detail": "Creator service unavailable"}, status=503)


@never_cache
@require_GET
def standing(request):
    if request.GET or request.body:
        return JsonResponse({"detail": "Invalid standing request"}, status=400)
    principal = authenticated_actor(request, require_verified_email=False)
    if isinstance(principal, JsonResponse):
        return principal
    actor, role = principal
    context = identity_context(request)
    if isinstance(context, JsonResponse):
        return context
    if context["account_id"] != actor:
        return JsonResponse({"detail": "Identity unavailable"}, status=503)
    creator = _creator_standing(actor, role)
    if isinstance(creator, JsonResponse):
        return creator
    from .moderation import _forward
    result = _forward("standing", actor, role, {"creator_id": creator["creator_id"]})
    if result.status_code != 200:
        return result
    return JsonResponse({"account_status": context["account_status"], "creator_status": creator["creator_status"],
                         "publishing_allowed": role in {"viewer", "creator"} and context["email_verified"] and creator["publishing_allowed"],
                         "notices": json.loads(result.content)["notices"]})
