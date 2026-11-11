"""Published following feed assembled from signed service reads."""

import json
from urllib.error import HTTPError
from uuid import UUID

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .accounts import current_account
from .internal_client import signed_internal_request
from .videos import _valid_item


def _read_page(audience, path, payload, limit):
    with signed_internal_request(audience, path, method="POST",
                                 payload=json.dumps(payload, separators=(",", ":")).encode()) as response:
        raw = response.read(limit + 1)
        if response.status != 200 or len(raw) > limit:
            raise ValueError("Invalid service response")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Invalid service response")
    return result


@never_cache
@require_GET
def following_videos(request):
    account = current_account(request)
    if account.status_code != 200:
        return account
    try:
        viewer = json.loads(account.content)
        account_id = str(UUID(viewer["id"]))
        if viewer["roles"] not in (["viewer"], ["creator"]):
            return JsonResponse({"detail": "Forbidden"}, status=403)
        if set(request.GET) - {"cursor"} or len(request.GET.getlist("cursor")) > 1:
            raise ValueError
        cursor = str(UUID(request.GET["cursor"])) if "cursor" in request.GET else None
        if request.body:
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({"detail": "Invalid following query"}, status=400)

    matches = []
    try:
        for _ in range(10):
            page = _read_page("content", "/internal/videos",
                              {"cursor": cursor} if cursor else {}, 1_000_000)
            if set(page) != {"items", "next_cursor"} or not isinstance(page["items"], list):
                raise ValueError("Invalid video page")
            videos = page["items"]
            next_cursor = page["next_cursor"]
            if len(videos) > 20 or any(not _valid_item(item) for item in videos):
                raise ValueError("Invalid video page")
            if len({item["id"] for item in videos}) != len(videos):
                raise ValueError("Repeated video")
            if next_cursor is not None and (
                not isinstance(next_cursor, str) or len(videos) != 20
                or next_cursor != videos[-1]["id"] or next_cursor == cursor
            ):
                raise ValueError("Invalid video cursor")
            creator_ids = sorted({item["creator_id"] for item in videos})
            membership = _read_page("engagement", "/internal/follows/membership",
                                    {"account_id": account_id, "creator_ids": creator_ids}, 2048)
            followed = membership.get("creator_ids")
            if (set(membership) != {"creator_ids"} or not isinstance(followed, list)
                    or followed != sorted(set(followed))
                    or any(value not in creator_ids for value in followed)):
                raise ValueError("Invalid membership response")
            for index, video in enumerate(videos):
                if video["creator_id"] in followed:
                    matches.append(video)
                if len(matches) == 20:
                    has_more = index < len(videos) - 1 or next_cursor is not None
                    return JsonResponse({"items": matches,
                                         "next_cursor": video["id"] if has_more else None})
            if next_cursor is None:
                return JsonResponse({"items": matches, "next_cursor": None})
            cursor = next_cursor
    except HTTPError as error:
        error.close()
        if error.code == 400:
            return JsonResponse({"detail": "Invalid following cursor"}, status=400)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    else:
        return JsonResponse({"items": matches, "next_cursor": cursor})
    return JsonResponse({"detail": "Following feed unavailable"}, status=503)
