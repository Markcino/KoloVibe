"""Verify the viewer and video before forwarding a like to engagement."""

import json
from uuid import UUID

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from .accounts import current_account
from .internal_client import signed_internal_request
from .videos import read_public_video


@require_http_methods(["PUT", "DELETE"])
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
    if liked:
        video = read_public_video(video_id)
        if video.status_code != 200:
            return video

    payload = json.dumps({"video_id": str(video_id), "account_id": account_id, "liked": liked}).encode()
    try:
        with signed_internal_request("engagement", "/internal/likes", method="POST", payload=payload) as response:
            if not liked and response.status == 204:
                return HttpResponse(status=204)
            if liked and response.status == 200:
                raw = response.read(257)
                if len(raw) <= 256:
                    result = json.loads(raw)
                    if (isinstance(result, dict) and set(result) == {"video_id", "liked"}
                            and result["video_id"] == str(video_id) and result["liked"] is True):
                        return JsonResponse(result)
    except (OSError, ValueError):
        pass
    return JsonResponse({"detail": "Engagement service unavailable"}, status=503)
