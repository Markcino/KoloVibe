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
        if not isinstance(result, dict) or set(result) != {
            "id", "user_id", "handle", "bio", "status"
        } or result["status"] != "active" or result["id"] != str(creator_id):
            raise ValueError("Invalid creator response")
        uuid.UUID(result["user_id"])
        if not isinstance(result["handle"], str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", result["handle"]):
            raise ValueError("Invalid creator handle")
        if not isinstance(result["bio"], str) or len(result["bio"]) > 500:
            raise ValueError("Invalid creator bio")
    except HTTPError as error:
        if error.code == 404:
            return JsonResponse({"detail": "Not found"}, status=404)
        return JsonResponse({"detail": "Creator service unavailable"}, status=503)
    except (URLError, OSError, TimeoutError, ValueError, TypeError, KeyError, UnicodeError):
        return JsonResponse({"detail": "Creator service unavailable"}, status=503)
    return JsonResponse(result)
