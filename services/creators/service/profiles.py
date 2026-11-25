"""Only reviewed active creator profiles are discoverable."""

import json
import re
import uuid

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from . import security_audit
from .models import CreatorProfile


def _public_profiles():
    return CreatorProfile.objects.filter(
        status=CreatorProfile.Status.ACTIVE,
        reviewed_at__isnull=False, restricted_at__isnull=True,
    )


def _profile_data(profile, *, with_account=True):
    """Profile fields. The internal account id is only for gateway authorization
    decisions (self-view, self-engagement); public search never carries it."""
    data = {"id": str(profile.id), "handle": profile.handle, "bio": profile.bio,
            "status": profile.status, "display_name": profile.display_name,
            "location": profile.location}
    if with_account:
        data["user_id"] = str(profile.user_id)
    return data


@require_POST
def internal_search(request):
    if len(request.body) > 1024:
        return JsonResponse({"detail": "Invalid search query"}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) - {"q", "cursor"}:
            raise ValueError
        query = data.get("q")
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100:
            raise ValueError
        query = query.strip()
        if any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in query):
            raise ValueError
        profiles = _public_profiles().filter(
            Q(handle__icontains=query) | Q(display_name__icontains=query)).order_by("id")
        if "cursor" in data:
            cursor = uuid.UUID(data["cursor"])
            if not profiles.filter(id=cursor).exists():
                raise ValueError
            profiles = profiles.filter(id__gt=cursor)
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"detail": "Invalid search query"}, status=400)
    page = list(profiles[:21])
    return JsonResponse({
        "items": [_profile_data(profile, with_account=False) for profile in page[:20]],
        "next_cursor": str(page[19].id) if len(page) > 20 else None,
    })


@require_POST
def internal_profile(request):
    if len(request.body) > 512:
        return JsonResponse({"detail": "Invalid request"}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"creator_id"}:
            raise ValueError("Invalid request")
        creator_id = uuid.UUID(data["creator_id"])
    except (ValueError, TypeError, KeyError, UnicodeError):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    profile = _public_profiles().filter(id=creator_id).first()
    if profile is None:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse(_profile_data(profile))


@require_POST
def own_profile(request):
    if getattr(request, "service_caller", None) != "gateway":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    try:
        if request.GET or len(request.body) > 8192:
            raise ValueError
        envelope = json.loads(request.body)
        if not isinstance(envelope, dict) or set(envelope) != {"actor_id", "role", "operation", "data"}:
            raise ValueError
        actor = uuid.UUID(envelope["actor_id"])
        if envelope["role"] != "creator":
            return JsonResponse({"detail": "Creator role required"}, status=403)
        operation, fields = envelope["operation"], envelope["data"]
        if (operation not in {"get", "patch"} or not isinstance(fields, dict)
                or set(fields) - {"display_name", "bio", "location", "handle"}
                or operation == "get" and fields or operation == "patch" and not fields):
            raise ValueError
        for name, value in fields.items():
            if (not isinstance(value, str) or len(value) > (500 if name == "bio" else 80)
                    or any((ord(c) < 32 and not (name == "bio" and c in "\n\r\t"))
                           or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
                raise ValueError
            if name == "handle" and not re.fullmatch(r"[a-z0-9_]{3,30}", value):
                raise ValueError
        with transaction.atomic():
            profile = CreatorProfile.objects.select_for_update().filter(user_id=actor).first()
            if profile is None:
                return JsonResponse({"detail": "Creator profile not found"}, status=404)
            if (profile.status != CreatorProfile.Status.ACTIVE or profile.reviewed_at is None
                    or profile.restricted_at is not None):
                return JsonResponse({"detail": "Creator profile unavailable"}, status=403)
            if "handle" in fields and CreatorProfile.objects.filter(
                handle__iexact=fields["handle"]).exclude(pk=profile.pk).exists():
                return JsonResponse({"detail": "Creator handle is unavailable", "code": "handle_taken"}, status=409)
            for name, value in fields.items():
                setattr(profile, name, value)
            if fields:
                profile.save(update_fields=list(fields))
                security_audit.record("creator.profile_updated", actor, "creator", profile.id)
        return JsonResponse(_profile_data(profile))
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        return JsonResponse({"detail": "Invalid creator profile"}, status=400)
    except IntegrityError:
        return JsonResponse({"detail": "Creator handle is unavailable", "code": "handle_taken"}, status=409)
    except DatabaseError:
        return JsonResponse({"detail": "Creator service unavailable"}, status=503)
