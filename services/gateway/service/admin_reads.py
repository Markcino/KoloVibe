import json
from urllib.error import HTTPError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from .creator_onboarding import authenticated_actor
from .standing import identity_context
from .internal_client import signed_internal_request


def principal(request):
    actor = authenticated_actor(request, require_verified_email=False)
    if isinstance(actor, JsonResponse):
        return actor
    account, role = actor
    if role not in {"moderator", "administrator"}:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    context = identity_context(request)
    if isinstance(context, JsonResponse):
        return context
    if context["account_id"] != account or context["mfa_verified"] is not True:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return account, role


def forward(audience, path, actor, role, data, validate):
    try:
        with signed_internal_request(audience, path, method="POST", timeout=12,
             payload=json.dumps({"actor_id": actor, "role": role, "mfa_verified": True, "data": data}).encode()) as response:
            raw = response.read(524289)
            value = json.loads(raw)
            if response.status == 200 and len(raw) <= 524288 and validate(value):
                return JsonResponse(value)
    except HTTPError as error:
        code = error.code
        error.close()
        if code in (400, 403, 404):
            return JsonResponse({"detail": "Request unavailable"}, status=code)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RuntimeError):
        pass
    return JsonResponse({"detail": "Service unavailable"}, status=503)


@never_cache
@require_GET
def fraud_holds(request):
    from .moderation import _forward
    from .admin_contracts import valid_holds
    actor = principal(request)
    if isinstance(actor, JsonResponse):
        return actor
    if request.body or set(request.GET) - {"cursor"} or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    cursor = request.GET.get("cursor")
    from uuid import UUID
    try:
        if cursor is not None and str(UUID(cursor)) != cursor:
            raise ValueError
    except ValueError:
        return JsonResponse({"detail": "Invalid request"}, status=400)
    scope = _forward("fraud_scope", *actor, {}, mfa_verified=True)
    if scope.status_code != 200:
        return scope
    return forward("engagement", "/internal/engagement/fraud-holds", *actor,
                   {"video_ids": json.loads(scope.content)["video_ids"], "cursor": cursor}, valid_holds)


@never_cache
@require_GET
def audit_log(request):
    from .admin_contracts import valid_audit_page
    actor = principal(request)
    if isinstance(actor, JsonResponse):
        return actor
    if (request.body or set(request.GET) - {"cursor", "kind", "producer", "since", "until"}
            or any(len(request.GET.getlist(key)) != 1 or len(request.GET[key]) > 100 for key in request.GET)):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    return forward("audit", "/internal/audit/read", *actor, dict(request.GET.items()), valid_audit_page)


@never_cache
@require_GET
def points_review(request, account_id=None):
    from .admin_contracts import valid_points_review
    actor = principal(request)
    if isinstance(actor, JsonResponse):
        return actor
    allowed = {"cursor", "as_of"} | ({"status"} if account_id else set())
    if (request.body or set(request.GET) - allowed
            or any(len(request.GET.getlist(key)) != 1 or len(request.GET[key]) > 100 for key in request.GET)):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    data = dict(request.GET.items())
    if account_id:
        data["account_id"] = str(account_id)
    return forward("points", "/internal/points/admin/" + ("account" if account_id else "balances"), *actor, data,
        lambda value: valid_points_review(value) and (account_id is None or value.get("account_id") == str(account_id)))


def _uuid_text(value):
    from uuid import UUID
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


@never_cache
@require_http_methods(["GET", "POST"])
def moderation_assignments(request):
    """Administrators list and set explicit moderator grants; Moderation owns every decision."""
    from .admin_contracts import valid_assignment, valid_assignment_list
    actor = principal(request)
    if isinstance(actor, JsonResponse):
        return actor
    account, role = actor
    if role != "administrator":
        return JsonResponse({"detail": "Forbidden"}, status=403)
    if request.method == "GET":
        values = {key: request.GET.getlist(key) for key in request.GET}
        if (request.body or set(values) != {"scope", "target"} or any(len(v) != 1 for v in values.values())
                or request.GET["scope"] not in {"videos", "reports", "appeals"} or not _uuid_text(request.GET["target"])):
            return JsonResponse({"detail": "Invalid request"}, status=400)
        scope, target = request.GET["scope"], request.GET["target"]
        return forward("moderation", "/internal/moderation/assignment_list", account, role,
                       {"scope": scope, "target_id": target},
                       lambda value: valid_assignment_list(value, scope, target))
    try:
        if request.GET or len(request.body) > 1024:
            raise ValueError
        data = json.loads(request.body)
        if (not isinstance(data, dict) or set(data) != {"scope", "target_id", "moderator_id", "active"}
                or data["scope"] not in {"videos", "reports", "appeals"} or type(data["active"]) is not bool
                or not _uuid_text(data["target_id"]) or not _uuid_text(data["moderator_id"])):
            raise ValueError
    except (ValueError, UnicodeError):
        return JsonResponse({"detail": "Invalid request"}, status=400)
    return forward("moderation", "/internal/moderation/assignment_set", account, role, data,
                   lambda value: valid_assignment(value, data))
