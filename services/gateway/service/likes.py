"""Verify the viewer and video before forwarding a like to engagement."""

import json
from uuid import UUID

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .accounts import current_account
from .internal_client import signed_internal_request
from .videos import read_public_video


@never_cache
@require_http_methods(["GET", "PUT", "DELETE"])
def video_like(request, video_id):
    account = current_account(request)
    if account.status_code != 200:
        return account

    try:
        profile = json.loads(account.content)
        account_id = str(UUID(profile["id"]))
        roles = profile["roles"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({"detail": "Identity unavailable"}, status=503)
    if roles not in (["viewer"], ["creator"]):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    if request.body or request.GET:
        return JsonResponse({"detail": "Invalid like request"}, status=400)

    liked = request.method == "PUT"
    if request.method != "DELETE":
        video = read_public_video(video_id)
        if video.status_code != 200:
            return video

    payload_data = {"video_id": str(video_id), "account_id": account_id}
    if request.method != "GET":
        payload_data["liked"] = liked
        if liked:
            try:
                payload_data["creator_id"] = str(UUID(json.loads(video.content)["creator_id"]))
            except (ValueError, TypeError, KeyError, AttributeError):
                return JsonResponse({"detail": "Content service unavailable"}, status=503)
    payload = json.dumps(payload_data).encode()
    path = "/internal/likes/status" if request.method == "GET" else "/internal/likes"
    try:
        with signed_internal_request("engagement", path, method="POST", payload=payload) as response:
            if response.status == 200:
                raw = response.read(257)
                if len(raw) <= 256:
                    result = json.loads(raw)
                    if (isinstance(result, dict) and set(result) == {"video_id", "liked", "like_count"}
                            and result["video_id"] == str(video_id)
                            and type(result["liked"]) is bool
                            and type(result["like_count"]) is int and result["like_count"] >= 0
                            and (request.method == "GET" or result["liked"] is liked)):
                        return JsonResponse(result)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    return JsonResponse({"detail": "Engagement service unavailable"}, status=503)
