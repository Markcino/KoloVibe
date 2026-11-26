"""Decision C: administrator review of privacy requests and account holds.

The gateway checks the caller's shape and every answer; Identity alone decides who may review, applies each step
and deactivates an account whose deletion is approved. Holds carry the administrator's private note, so these routes
are for the console only and never for the app.
"""
import json
import re
import uuid

from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .accounts import _bearer, _body, _invoke, _json

PATH = "/internal/auth/privacy-review"
STATUSES = {"received", "in_review", "processing", "completed", "declined"}
DECLINE_CODES = {"IDENTITY_NOT_CONFIRMED", "DUPLICATE_REQUEST", "WITHDRAWN"}
HOLD_REASONS = {"LEGAL_CLAIM", "AUTHORITY_REQUEST", "FRAUD_INVESTIGATION"}
STEPS = {"review": "start-review", "decline": "decline", "approve-deletion": "approve-deletion"}
CONFLICTS = {"request_not_received", "request_not_in_review", "request_not_deletion", "own_account",
             "account_on_hold"}
ZONED = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)")


def _id(value):
    return isinstance(value, str) and str(uuid.UUID(value)) == value


def _time(value, nullable=False):
    return value is None and nullable or isinstance(value, str) and ZONED.fullmatch(value) is not None


def valid_request(item):
    return (isinstance(item, dict)
            and set(item) == {"id", "account_id", "kind", "status", "created_at", "review_started_at",
                              "decided_at", "decline_code", "held"}
            and _id(item["id"]) and _id(item["account_id"]) and item["kind"] in {"access", "deletion"}
            and item["status"] in STATUSES and _time(item["created_at"])
            and _time(item["review_started_at"], True) and _time(item["decided_at"], True)
            and (item["decline_code"] in DECLINE_CODES) == (item["status"] == "declined")
            and (item["decline_code"] is None or item["status"] == "declined")
            and type(item["held"]) is bool)


def valid_hold(item):
    return (isinstance(item, dict)
            and set(item) == {"id", "account_id", "reason_code", "note", "placed_by", "placed_at", "released_at"}
            and _id(item["id"]) and _id(item["account_id"]) and _id(item["placed_by"])
            and item["reason_code"] in HOLD_REASONS and isinstance(item["note"], str)
            and 3 <= len(item["note"]) <= 500 and _time(item["placed_at"]) and _time(item["released_at"], True))


def valid_page(data):
    return (set(data) == {"items", "next_cursor"} and isinstance(data["items"], list) and len(data["items"]) <= 50
            and all(valid_request(item) for item in data["items"])
            and (data["next_cursor"] is None or _id(data["next_cursor"])))


def valid_holds(data):
    return (set(data) == {"items"} and isinstance(data["items"], list) and len(data["items"]) <= 50
            and all(valid_hold(item) for item in data["items"]))


def _forward(token, operation, fields, statuses, validator):
    response = _invoke(PATH, {"access_token": token, "operation": operation, **fields}, statuses)
    if response.status_code in statuses:
        try:
            valid = validator(json.loads(response.content))
        except (ValueError, TypeError, KeyError, AttributeError):
            valid = False
        if not valid:
            return _json({"detail": "Identity unavailable"}, 503)
    return response


def _token(request):
    return _bearer(request)


@never_cache
@require_http_methods(["GET"])
def collection(request):
    token = _token(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    fields = {}
    try:
        if set(request.GET) - {"status", "cursor"} or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
            raise ValueError
        if "status" in request.GET:
            if request.GET["status"] not in STATUSES:
                raise ValueError
            fields["status"] = request.GET["status"]
        if "cursor" in request.GET:
            fields["cursor"] = str(uuid.UUID(request.GET["cursor"]))
    except ValueError:
        return _json({"detail": "Invalid filters"}, 400)
    return _forward(token, "list", fields, {200}, valid_page)


@never_cache
@require_POST
def step(request, operation, target_id):
    token = _token(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    try:
        data = _body(request, {"decline_code"}) if request.body else {}
        if operation == "decline":
            if set(data) != {"decline_code"} or data["decline_code"] not in DECLINE_CODES:
                raise ValueError
        elif data:
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        return _json({"detail": "Invalid privacy review request"}, 400)
    return _forward(token, STEPS[operation], {"id": str(target_id), **data}, {200}, valid_request)


@never_cache
@require_http_methods(["GET", "POST"])
def holds(request, target_id):
    token = _token(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    if request.method == "GET":
        if request.GET:
            return _json({"detail": "Invalid filters"}, 400)
        return _forward(token, "holds", {"account_id": str(target_id)}, {200}, valid_holds)
    try:
        data = _body(request, {"reason_code", "note"})
        if (set(data) != {"reason_code", "note"} or data["reason_code"] not in HOLD_REASONS
                or not isinstance(data["note"], str) or not 3 <= len(data["note"].strip()) <= 500):
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        return _json({"detail": "Invalid hold"}, 400)
    return _forward(token, "hold-place", {"account_id": str(target_id), **data}, {200, 201}, valid_hold)


@never_cache
@require_POST
def release(request, target_id):
    token = _token(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    if request.body:
        return _json({"detail": "Invalid hold"}, 400)
    return _forward(token, "hold-release", {"id": str(target_id)}, {200}, valid_hold)
