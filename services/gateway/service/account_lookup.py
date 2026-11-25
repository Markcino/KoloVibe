"""Administrator-only account lookup for creator invitations; Identity owns every decision."""

import json

from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .accounts import _bearer, _body, _invoke, _json
from .invitation_contracts import identifier


def valid_candidate(value):
    return (isinstance(value, dict) and set(value) == {"account_id", "display_name", "role", "email_verified"}
            and identifier(value["account_id"]) and isinstance(value["display_name"], str)
            and 1 <= len(value["display_name"]) <= 80 and value["role"] in ("viewer", "creator")
            and type(value["email_verified"]) is bool)


@never_cache
@require_POST
def lookup(request):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    try:
        data = _body(request, {"email"})
        if set(data) != {"email"}:
            raise ValueError
        forwarded = {"access_token": token, "email": data["email"]}
    except (ValueError, UnicodeError):
        # Authority is Identity's decision and must come first: forward the token alone, so a caller without authority is refused
        # whatever the body and an administrator receives Identity's validation error. Nothing the caller chose is passed on.
        forwarded = {"access_token": token}
    response = _invoke("/internal/auth/account-lookup", forwarded, {200}, max_response=4096)
    if response.status_code == 200 and not valid_candidate(json.loads(response.content)):
        return _json({"detail": "Identity unavailable"}, 503)
    return response
