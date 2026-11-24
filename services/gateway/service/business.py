"""Business routes: authenticate, gate and forward. All business rules, validation and authorization live in the
Business service (one implementation); the Gateway adds nothing a second copy could drift from.

What the Gateway does: validate the session with Identity (live, never cached), require a verified email or an
MFA session where the operation says so, bound the request, refuse path/body id collisions, bind the actor from the
session (never from the request), sign the call, and return a bounded JSON object.
"""
import json
from urllib.error import HTTPError

from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache

from uuid import UUID

from .accounts import _bearer, _client_origin, _invoke
from .admin_reads import principal
from .creator_onboarding import authenticated_actor
from .internal_client import signed_internal_request
from .responses import error_response as _error

MAX_BODY = 4096
MAX_RESPONSE = 65536
PASS_THROUGH = {400, 403, 404, 409, 429}

# operation -> (methods, who, verified_email, allowed query parameters)
OPERATIONS = {
    "register": (("POST",), "customer", True, ()),
    "list_mine": (("GET",), "customer", False, ("cursor", "limit")),
    "get_mine": (("GET",), "customer", False, ()),
    "staff_invite": (("POST",), "customer", False, ()),
    "staff_invitation_revoke": (("DELETE",), "customer", False, ()),
    "staff_redeem": (("POST",), "customer", True, ()),
    "member_list": (("GET",), "customer", False, ()),
    "member_remove": (("DELETE",), "customer", False, ()),
    "member_leave": (("POST",), "customer", False, ()),
    "registration_grant": (("PUT",), "privileged", False, ()),
    "verification_submit": (("POST",), "customer", False, ()),
    "verification_respond": (("POST",), "customer", False, ()),
    "verification_status": (("GET",), "customer", False, ()),
    "verification_queue": (("GET",), "privileged", False, ("cursor", "limit")),
    "verification_case": (("GET",), "privileged", False, ()),
    "verification_claim": (("POST",), "privileged", False, ()),
    "verification_decide": (("POST",), "privileged", False, ()),
    "reviewer_grant": (("PUT",), "privileged", False, ()),
    "profile_get": (("GET",), "customer", False, ()),
    "profile_edit": (("PATCH",), "customer", False, ()),
    "profile_submit": (("POST",), "customer", False, ()),
    "hours_replace": (("PUT",), "customer", False, ()),
    "category_list": (("GET",), "public", False, ()),
    "listing_status": (("GET",), "customer", False, ()),
    "listing_publish": (("POST",), "customer", False, ()),
    "listing_unpublish": (("POST",), "customer", False, ()),
    "public_search": (("GET",), "public", False, ("q", "category", "county", "city", "open_now", "verified", "sort", "cursor", "limit")),
    "public_detail": (("GET",), "public", False, ()),
    "inquiry_create": (("POST",), "customer", True, ()),
    "inquiry_list_mine": (("GET",), "customer", False, ("cursor", "limit")),
    "inquiry_get_mine": (("GET",), "customer", False, ()),
    "inquiry_message_customer": (("POST",), "customer", True, ()),
    "inquiry_close_customer": (("POST",), "customer", False, ()),
    "inquiry_confirm_customer": (("POST",), "customer", False, ()),
    "inquiry_inbox": (("GET",), "customer", False, ("cursor", "limit")),
    "inquiry_inbox_get": (("GET",), "customer", False, ()),
    "inquiry_reply": (("POST",), "customer", False, ()),
    "inquiry_close_business": (("POST",), "customer", False, ()),
    "inquiry_confirm_business": (("POST",), "customer", False, ()),
    "inquiry_block": (("POST",), "customer", False, ()),
    "review_list_public": (("GET",), "public", False, ("cursor", "limit")),
    "review_create": (("POST",), "customer", True, ()),
    "review_list_mine": (("GET",), "customer", False, ("cursor", "limit")),
    "review_edit_mine": (("PATCH",), "customer", True, ()),
    "review_withdraw_mine": (("DELETE",), "customer", False, ()),
    "review_respond": (("PUT",), "customer", False, ()),
    "review_response_delete": (("DELETE",), "customer", False, ()),
    "review_invite_create": (("POST",), "customer", False, ()),
    "review_invite_revoke": (("DELETE",), "customer", False, ()),
    "report_create": (("POST",), "customer", True, ()),
    "report_queue": (("GET",), "privileged", False, ("cursor", "limit")),
    "report_case": (("GET",), "privileged", False, ()),
    "report_decide": (("POST",), "privileged", False, ()),
    "category_put": (("PUT",), "privileged", False, ()),
    "profile_queue": (("GET",), "privileged", False, ("cursor", "limit")),
    "profile_revision": (("GET",), "privileged", False, ()),
    "profile_decide": (("POST",), "privileged", False, ()),
}


def _data(request, query, ids):
    if request.method in ("GET", "DELETE"):
        if request.body:
            raise ValueError
        if set(request.GET) - set(query) or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
            raise ValueError
        body = dict(request.GET.items())
    else:
        if request.GET or len(request.body) > MAX_BODY:
            raise ValueError
        body = json.loads(request.body) if request.body else {}
        if not isinstance(body, dict):
            raise ValueError
    if set(body) & set(ids):  # the path names the object; a body must not try to name another
        raise ValueError
    return {**body, **ids}


NIL_ACTOR = "00000000-0000-0000-0000-000000000000"


def _optional_session(request):
    """Public routes: no credential means anonymous; a credential that is present must be valid (never downgraded).

    One live Identity validation (no cache) also tells us whether the email is verified, which gates contact reveal.
    """
    if "Authorization" not in request.headers:
        return NIL_ACTOR, "anonymous", False
    token = _bearer(request)
    if token is None:
        return _error("Unauthorized", 401)
    result = _invoke("/internal/auth/validate", {"access_token": token, "include_email_verification": True}, {200})
    if result.status_code != 200:
        return result
    try:
        payload = json.loads(result.content)
        user, roles = payload["user"], payload["user"]["roles"]
        if len(roles) != 1 or not isinstance(roles[0], str) or type(payload["email_verified"]) is not bool:
            raise ValueError
        return str(UUID(user["id"])), roles[0], payload["email_verified"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return _error("Identity unavailable", 503)


def _forward(operation, actor, role, *, mfa, verified, key, data, origin=None):
    envelope = {"actor_id": actor, "role": role, "mfa_verified": mfa, "email_verified": verified,
                "idempotency_key": key, "origin": origin, "data": data}
    try:
        with signed_internal_request("business", f"/internal/business/{operation}", method="POST", timeout=12,
                                     payload=json.dumps(envelope, separators=(",", ":")).encode()) as response:
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) <= MAX_RESPONSE and response.status in (200, 201, 204):
                if response.status == 204:
                    return HttpResponse(status=204)
                result = json.loads(raw)
                if isinstance(result, dict):
                    return JsonResponse(result, status=response.status)
    except HTTPError as error:
        with error:
            if error.code in PASS_THROUGH:
                try:
                    raw = error.read(513)
                    result = json.loads(raw) if len(raw) <= 512 else None
                    if (isinstance(result, dict) and {"detail"} <= set(result) <= {"detail", "code"}
                            and all(isinstance(v, str) for v in result.values())):
                        return JsonResponse(result, status=error.code)
                except (OSError, ValueError, TypeError, AttributeError):
                    pass
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
        pass
    return _error("Business service unavailable", 503)


@never_cache
def business_endpoint(request, operations, **ids):
    """`operations` maps an HTTP method to an operation name for this route."""
    operation = operations.get(request.method)
    if operation is None:
        return HttpResponseNotAllowed(sorted(operations))
    _, who, verified, query = OPERATIONS[operation]
    key = request.headers.get("Idempotency-Key")
    if key is not None and not 16 <= len(key) <= 128:
        return _error("Invalid request", 400)
    if who == "privileged":
        actor = principal(request)
    elif who == "public":
        actor = _optional_session(request)
        if isinstance(actor, JsonResponse):
            return actor
        actor, role, verified = actor
        actor = (actor, role)
    else:
        actor = authenticated_actor(request, require_verified_email=verified)
    if isinstance(actor, JsonResponse):
        return actor
    try:
        data = _data(request, query, {name: str(value) for name, value in ids.items()})
    except (ValueError, TypeError, UnicodeError):
        return _error("Invalid request", 400)
    return _forward(operation, actor[0], actor[1], mfa=who == "privileged", verified=verified, key=key, data=data,
                    origin=_client_origin(request))
