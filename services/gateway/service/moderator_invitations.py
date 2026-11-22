"""Bounded forwarding; Identity alone grants moderator accounts and consumes invitations."""

import json
import re
import uuid

from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods

from .accounts import _bearer, _body, _invoke, _json
from .invitation_contracts import valid_receipt, valid_page, valid_setup, valid_complete


def checked(path, data, status, validator):
    response = _invoke(path, data, {status}, max_response=32768)
    if response.status_code == status and status != 204:
        if not validator(json.loads(response.content)):
            return _json({"detail": "Identity unavailable"}, 503)
    return response


@never_cache
@require_http_methods(["GET", "POST"])
def collection(request):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    if request.method == "GET":
        if set(request.GET) - {"cursor"} or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
            return _json({"detail": "Invalid filters"}, 400)
        cursor = request.GET.get("cursor")
        if cursor:
            try:
                uuid.UUID(cursor)
            except ValueError:
                return _json({"detail": "Invalid cursor"}, 400)
        return checked("/internal/auth/moderator-invitations", {"access_token": token, "operation": "list",
                       **({"cursor": cursor} if cursor else {})}, 200, valid_page)
    try:
        data = _body(request, {"email", "display_name", "reason"})
        key = request.headers.get("Idempotency-Key", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid invitation request"}, 400)
    return checked("/internal/auth/moderator-invitations", {**data, "access_token": token,
                   "operation": "create", "key": key}, 202, valid_receipt)


@never_cache
@require_POST
def revoke(request, invitation_id):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    try:
        data = _body(request, {"reason"})
        key = request.headers.get("Idempotency-Key", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid invitation request"}, 400)
    return checked("/internal/auth/moderator-invitations", {**data, "access_token": token,
                   "operation": "revoke", "id": str(invitation_id), "key": key}, 204, None)


@never_cache
@require_POST
def accept(request, complete=False):
    try:
        data = _body(request, {"invitation_code", "email", "code"} if complete
                     else {"invitation_code", "email", "password"})
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid invitation"}, 400)
    operation = "complete" if complete else "setup"
    return checked("/internal/auth/moderator-invitations/" + operation, data, 200,
                   valid_complete if complete else valid_setup)
