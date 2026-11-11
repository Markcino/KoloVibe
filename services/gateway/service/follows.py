"""Account-bound follow operations for reviewed creator profiles."""

import json
from urllib.error import HTTPError
from uuid import UUID

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .accounts import current_account
from .creators import read_creator
from .internal_client import signed_internal_request


@never_cache
@require_http_methods(["GET", "PUT", "DELETE"])
def creator_follow(request, creator_id):
    account = current_account(request)
    if account.status_code != 200:
        return account
    if request.GET or request.body:
        return JsonResponse({"detail": "Invalid follow request"}, status=400)
    try:
        viewer = json.loads(account.content)
        account_id = str(UUID(viewer["id"]))
        if viewer["roles"] not in (["viewer"], ["creator"]):
            return JsonResponse({"detail": "Forbidden"}, status=403)
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({"detail": "Identity unavailable"}, status=503)

    if request.method == "PUT":
        creator = read_creator(creator_id)
        if creator.status_code != 200:
            return creator
        if json.loads(creator.content)["user_id"] == account_id:
            return JsonResponse({"detail": "Cannot follow your own profile"}, status=403)

    operation = {"PUT": "follow", "DELETE": "unfollow", "GET": "status"}[request.method]
    payload = json.dumps({"account_id": account_id, "creator_id": str(creator_id),
                          "operation": operation}, separators=(",", ":")).encode()
    try:
        with signed_internal_request("engagement", "/internal/follows", method="POST",
                                     payload=payload) as response:
            if request.method == "DELETE" and response.status == 204:
                return HttpResponse(status=204)
            if request.method != "DELETE" and response.status == 200:
                raw = response.read(257)
                result = json.loads(raw) if len(raw) <= 256 else None
                if (isinstance(result, dict) and set(result) == {"creator_id", "following"}
                        and result["creator_id"] == str(creator_id)
                        and type(result["following"]) is bool
                        and (request.method != "PUT" or result["following"])):
                    return JsonResponse(result)
    except HTTPError as error:
        error.close()
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return JsonResponse({"detail": "Engagement service unavailable"}, status=503)
