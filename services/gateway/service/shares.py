"""App-link share URLs (owner decision SIM-02) and authenticated daily share-intent recording."""

import json
from uuid import UUID

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .accounts import current_account
from .app_links import share_url
from .internal_client import signed_internal_request
from .videos import read_public_video


def _unavailable():
    return JsonResponse({"detail": "Sharing is unavailable", "code": "share_unavailable"}, status=503)


@never_cache
@require_POST
def video_share(request, video_id):
    account = current_account(request)
    if account.status_code != 200:
        return account
    try:
        viewer = json.loads(account.content)
        account_id = str(UUID(viewer["id"]))
        if viewer["roles"] not in (["viewer"], ["creator"]):
            return JsonResponse({"detail": "Forbidden"}, status=403)
    except (ValueError, TypeError, KeyError, AttributeError):
        return _unavailable()
    if request.GET or request.body:
        return JsonResponse({"detail": "Invalid share request"}, status=400)
    video = read_public_video(video_id)
    if video.status_code != 200:
        return video
    link = share_url(video_id)
    if link is None:
        return _unavailable()
    try:
        creator_id = str(UUID(json.loads(video.content)["creator_id"]))
        payload = {"account_id": account_id, "video_id": str(video_id), "creator_id": creator_id}
        with signed_internal_request("engagement", "/internal/engagement/shares", method="POST", timeout=2,
                                     payload=json.dumps(payload, separators=(",", ":")).encode()) as response:
            raw = response.read(257)
            if response.status != 200 or len(raw) > 256:
                return _unavailable()
        result = json.loads(raw)
        if (not isinstance(result, dict) or set(result) != {"video_id", "recorded"}
                or result["video_id"] != str(video_id) or result["recorded"] is not True):
            return _unavailable()
        return JsonResponse({"video_id": str(video_id), "share_url": link})
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return _unavailable()
