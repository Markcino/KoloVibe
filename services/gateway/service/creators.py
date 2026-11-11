"""Public creator reads through the signed, private creator-service boundary."""

import json
import re
import uuid
from urllib.error import HTTPError, URLError

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .internal_client import signed_internal_request


@require_GET
def creator_detail(request, creator_id):
    return read_creator(creator_id)


def read_creator(creator_id):
    try:
        response = signed_internal_request(
            "creators", "/internal/creators/profile", method="POST",
            payload=json.dumps({"creator_id": str(creator_id)}, separators=(",", ":")).encode(),
        )
        with response:
            if response.status != 200:
                raise ValueError("Unexpected creator response")
            raw = response.read(4097)
        if len(raw) > 4096:
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


def _validate_profile(result):
    if not isinstance(result, dict) or set(result) != {
        "id", "user_id", "handle", "bio", "status"
    } or result["status"] != "active":
        raise ValueError("Invalid creator response")
    if not all(isinstance(result[key], str) for key in ("id", "user_id")):
        raise ValueError("Invalid creator identifier")
    uuid.UUID(result["user_id"])
    uuid.UUID(result["id"])
    if not isinstance(result["handle"], str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", result["handle"]):
        raise ValueError("Invalid creator handle")
    if not isinstance(result["bio"], str) or len(result["bio"]) > 500:
        raise ValueError("Invalid creator bio")


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
            raw = response.read(131073)
            if response.status != 200 or len(raw) > 131072:
                raise ValueError
        page = json.loads(raw)
        if not isinstance(page, dict) or set(page) != {"items", "next_cursor"}:
            raise ValueError
        items = page["items"]
        if not isinstance(items, list) or len(items) > 20:
            raise ValueError
        for item in items:
            _validate_profile(item)
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
