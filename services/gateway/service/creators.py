"""Public creator reads through the signed, private creator-service boundary."""

import json
import re
import uuid
from urllib.error import HTTPError, URLError

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

from .internal_client import signed_internal_request
from .creator_onboarding import authenticated_actor
from . import content_client, engagement_client


@never_cache
@require_GET
def creator_detail(request, creator_id):
    result = read_creator(creator_id)
    if result.status_code != 200:
        return result
    count = content_client.published_video_count(str(creator_id))
    try:
        followers = engagement_client.follower_count(str(creator_id))
    except (OSError, RuntimeError, ValueError):
        followers = None
    if count is None or followers is not None and (type(followers) is not int or followers < 0):
        return JsonResponse({"detail": "Creator totals unavailable"}, status=503)
    return JsonResponse(public_profile(json.loads(result.content))
                        | {"published_video_count": count, "follower_count": followers})


def public_profile(profile):
    """Fields safe for anonymous clients: never the internal account id."""
    return {key: value for key, value in profile.items() if key != "user_id"}


def read_creator(creator_id):
    try:
        response = signed_internal_request(
            "creators", "/internal/creators/profile", method="POST",
            payload=json.dumps({"creator_id": str(creator_id)}, separators=(",", ":")).encode(),
        )
        with response:
            if response.status != 200:
                raise ValueError("Unexpected creator response")
            raw = response.read(16385)
        if len(raw) > 16384:
            raise ValueError("Creator response too large")
        result = json.loads(raw)
        _validate_profile(result)
        if result["id"] != str(creator_id):
            raise ValueError("Mismatched creator response")
    except HTTPError as error:
        if error.code == 404:
            return JsonResponse({"detail": "Not found"}, status=404)
        return JsonResponse({"detail": "Creator service unavailable"}, status=503)
    except (URLError, OSError, TimeoutError, ValueError, TypeError, KeyError, UnicodeError):
        return JsonResponse({"detail": "Creator service unavailable"}, status=503)
    return JsonResponse(result)


_PUBLIC_FIELDS = {"id", "handle", "bio", "status", "display_name", "location"}


def _validate_profile(result, *, with_account=True):
    expected = _PUBLIC_FIELDS | {"user_id"} if with_account else _PUBLIC_FIELDS
    if not isinstance(result, dict) or set(result) != expected or result["status"] != "active":
        raise ValueError("Invalid creator response")
    if not all(isinstance(result[key], str) for key in expected & {"id", "user_id"}):
        raise ValueError("Invalid creator identifier")
    if with_account:
        uuid.UUID(result["user_id"])
    uuid.UUID(result["id"])
    if not isinstance(result["handle"], str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", result["handle"]):
        raise ValueError("Invalid creator handle")
    if not isinstance(result["bio"], str) or len(result["bio"]) > 500:
        raise ValueError("Invalid creator bio")
    for field in ("display_name", "location"):
        if not isinstance(result[field], str) or len(result[field]) > 80:
            raise ValueError("Invalid creator profile")


@never_cache
@require_http_methods(["GET", "PATCH"])
def own_creator(request):
    actor = authenticated_actor(request, require_verified_email=True)
    if isinstance(actor, JsonResponse):
        return actor
    if actor[1] != "creator":
        return JsonResponse({"detail": "Creator role required"}, status=403)
    try:
        if request.GET or len(request.body) > 8192 or request.method == "GET" and request.body:
            raise ValueError
        fields = json.loads(request.body) if request.method == "PATCH" else {}
        if (not isinstance(fields, dict) or set(fields) - {"display_name", "bio", "location", "handle"}
                or request.method == "PATCH" and not fields):
            raise ValueError
        for name, value in fields.items():
            if (not isinstance(value, str) or len(value) > (500 if name == "bio" else 80)
                    or name == "handle" and not re.fullmatch(r"[a-z0-9_]{3,30}", value)
                    or any((ord(c) < 32 and not (name == "bio" and c in "\n\r\t"))
                           or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
                raise ValueError
    except (ValueError, TypeError, UnicodeError):
        return JsonResponse({"detail": "Invalid creator profile"}, status=400)
    envelope = {"actor_id": actor[0], "role": actor[1], "operation": "patch" if fields else "get", "data": fields}
    try:
        with signed_internal_request("creators", "/internal/creators/me", method="POST",
                                     payload=json.dumps(envelope).encode()) as response:
            raw = response.read(16385)
            if response.status != 200 or len(raw) > 16384:
                raise ValueError
        data = json.loads(raw)
        _validate_profile(data)
        if data["user_id"] != actor[0] or any(data[name] != value for name, value in fields.items()):
            raise ValueError
        return JsonResponse(data)
    except HTTPError as error:
        with error:
            if error.code in {400, 403, 404, 409}:
                try:
                    raw = error.read(513)
                    data = json.loads(raw)
                    if (len(raw) <= 512 and isinstance(data, dict)
                            and isinstance(data.get("detail"), str) and len(data["detail"]) <= 160):
                        result = {"detail": data["detail"]}
                        if error.code == 409 and data.get("code") == "handle_taken":
                            result["code"] = "handle_taken"
                        return JsonResponse(result, status=error.code)
                except (ValueError, TypeError, UnicodeError):
                    pass
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    return JsonResponse({"detail": "Creator service unavailable"}, status=503)


@require_GET
def search_creators(request):
    try:
        if set(request.GET) - {"q", "cursor"} or any(
            len(request.GET.getlist(key)) != 1 for key in request.GET
        ):
            raise ValueError
        query = request.GET.get("q", "").strip()
        if not 1 <= len(query) <= 100 or any(ord(char) < 32 for char in query):
            raise ValueError
        payload = {"q": query}
        if "cursor" in request.GET:
            payload["cursor"] = str(uuid.UUID(request.GET["cursor"]))
    except ValueError:
        return JsonResponse({"detail": "Invalid search query"}, status=400)
    try:
        with signed_internal_request(
            "creators", "/internal/creators/search", method="POST",
            payload=json.dumps(payload).encode(),
        ) as response:
            raw = response.read(262145)
            if response.status != 200 or len(raw) > 262144:
                raise ValueError
        page = json.loads(raw)
        if not isinstance(page, dict) or set(page) != {"items", "next_cursor"}:
            raise ValueError
        items = page["items"]
        if not isinstance(items, list) or len(items) > 20:
            raise ValueError
        for item in items:
            _validate_profile(item, with_account=False)
        ids = [uuid.UUID(item["id"]) for item in items]
        if ids != sorted(set(ids)) or (
            ids and "cursor" in payload and ids[0] <= uuid.UUID(payload["cursor"])
        ):
            raise ValueError
        cursor = page["next_cursor"]
        if cursor is not None and (len(items) != 20 or cursor != items[-1]["id"]):
            raise ValueError
    except HTTPError as error:
        error.close()
        if error.code == 400:
            return JsonResponse({"detail": "Invalid search query"}, status=400)
        return JsonResponse({"detail": "Creator service unavailable"}, status=503)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return JsonResponse({"detail": "Creator service unavailable"}, status=503)
    return JsonResponse(page)
