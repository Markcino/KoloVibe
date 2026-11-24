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


def _forward(operation, actor, role, *, mfa, verified, key, data):
    envelope = {"actor_id": actor, "role": role, "mfa_verified": mfa, "email_verified": verified,
                "idempotency_key": key, "data": data}
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
    else:
        actor = authenticated_actor(request, require_verified_email=verified)
    if isinstance(actor, JsonResponse):
        return actor
    try:
        data = _data(request, query, {name: str(value) for name, value in ids.items()})
    except (ValueError, TypeError, UnicodeError):
        return _error("Invalid request", 400)
    return _forward(operation, actor[0], actor[1], mfa=who == "privileged", verified=verified, key=key, data=data)
