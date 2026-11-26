"""Decision C: administrators review privacy requests and manage account holds.

Identity decides who may act (administrator, MFA within five minutes for a change) and applies each step. This page
validates every answer, never echoes Identity's error text, and carries a signed, session-bound intent per change.
Approving a deletion deactivates the account, revokes its sessions and starts erasure in each participating service
(Decision C slices 2a to 2c: Engagement, Creators, Moderation and Content). The page never offers "completed" and says so.
"""

from datetime import datetime
from urllib.parse import urlencode

from django.core import signing
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse

from . import views
from .api_contracts import valid_id

SALT = "admin-privacy-review"
NOTICE = "privacy_review_notice"
STATUSES = ("received", "in_review", "processing", "completed", "declined")
STATUS_LABELS = {"received": "Received", "in_review": "In review", "processing": "Approved, erasure pending",
                 "completed": "Completed", "declined": "Declined"}
DECLINE = {"IDENTITY_NOT_CONFIRMED": "Identity could not be confirmed", "DUPLICATE_REQUEST": "Duplicate request",
           "WITHDRAWN": "Withdrawn by the person"}
HOLD_REASONS = {"LEGAL_CLAIM": "Legal claim or dispute", "AUTHORITY_REQUEST": "Request from a competent authority",
                "FRAUD_INVESTIGATION": "Fraud or security investigation"}
ROW = {"id", "account_id", "kind", "status", "created_at", "review_started_at", "decided_at", "decline_code", "held"}
HOLD = {"id", "account_id", "reason_code", "note", "placed_by", "placed_at", "released_at"}
UNAVAILABLE = "Privacy requests are unavailable right now. They may not be enabled in this environment."
CONFLICT = {"request_not_received": "This request is no longer waiting for review.",
            "request_not_in_review": "Open the review before deciding.",
            "request_not_deletion": "Only a deletion request can be approved here. Access exports come later.",
            "own_account": "You can't approve the deletion of your own account.",
            "account_on_hold": "This account is on hold. Release the hold before approving the deletion."}
REFUSED = {400: "Check the form and try again.", 403: "Sign in again with your authenticator to make this change.",
           404: "That request, account or hold wasn't found."}


def _stamp(value, nullable=False):
    if value is None:
        return nullable
    try:
        return isinstance(value, str) and len(value) <= 64 and datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def valid_row(item):
    try:
        return (isinstance(item, dict) and set(item) == ROW and valid_id(item["id"]) and valid_id(item["account_id"])
                and item["kind"] in ("access", "deletion") and item["status"] in STATUSES
                and _stamp(item["created_at"]) and _stamp(item["review_started_at"], True)
                and _stamp(item["decided_at"], True) and type(item["held"]) is bool
                and (item["decline_code"] in DECLINE) == (item["status"] == "declined")
                and (item["decline_code"] is None or item["decline_code"] in DECLINE))
    except (TypeError, KeyError):
        return False


def valid_hold(item):
    try:
        return (isinstance(item, dict) and set(item) == HOLD and valid_id(item["id"]) and valid_id(item["account_id"])
                and valid_id(item["placed_by"]) and item["reason_code"] in HOLD_REASONS
                and isinstance(item["note"], str) and 3 <= len(item["note"]) <= 500
                and _stamp(item["placed_at"]) and _stamp(item["released_at"], True))
    except (TypeError, KeyError):
        return False


def _proof(request, operation, target):
    return views._intent(request, "privacy-" + operation, target)


def _intent(request, operation, target):
    return signing.dumps(_proof(request, operation, target), salt=SALT)


def _valid_intent(request, operation, target):
    try:
        return signing.loads(request.POST.get("intent", ""), salt=SALT, max_age=900) == _proof(request, operation, target)
    except (signing.BadSignature, TypeError, ValueError):
        return False


def _refusal(code, result):
    if code == 409 and isinstance(result, dict) and result.get("code") in CONFLICT:
        return CONFLICT[result["code"]]
    return REFUSED.get(code, UNAVAILABLE)


def _administrator(request):
    return request.admin_account["roles"] == ["administrator"]


def _rows_with_actions(request, items):
    rows = []
    for item in items:
        actions = {}
        if item["status"] == "received":
            actions["review"] = _intent(request, "review", item["id"])
        if item["status"] == "in_review":
            actions["decline"] = _intent(request, "decline", item["id"])
            if item["kind"] == "deletion" and not item["held"]:
                actions["approve"] = _intent(request, "approve-deletion", item["id"])
        rows.append({**item, "actions": actions, "status_label": STATUS_LABELS[item["status"]],
                     "decline_label": DECLINE.get(item["decline_code"])})
    return rows


def _list(request, *, error=None, status=200):
    query = {k: request.GET[k] for k in ("status", "cursor") if k in request.GET}
    code, page = views._api("/admin/privacy-requests" + ("?" + urlencode(query) if query else ""),
                            token=request.gateway_token, response_limit=262144)
    if code == 401:
        return views._expired(request)
    available = (code == 200 and isinstance(page, dict) and set(page) == {"items", "next_cursor"}
                 and isinstance(page["items"], list) and len(page["items"]) <= 50
                 and all(valid_row(item) for item in page["items"])
                 and (page["next_cursor"] is None or valid_id(page["next_cursor"])))
    next_query = (urlencode({**query, "cursor": page["next_cursor"]})
                  if available and page["next_cursor"] else None)
    return views._render(request, "privacy_requests.html", {
        "title": "Privacy requests", "rows": _rows_with_actions(request, page["items"]) if available else [],
        "available": available, "statuses": [(s, STATUS_LABELS[s]) for s in STATUSES],
        "selected": query.get("status"), "decline_codes": DECLINE.items(), "next_query": next_query,
        "error": error or (None if available else UNAVAILABLE), "notice": request.session.pop(NOTICE, None)},
        status=status)


@views.privileged
def privacy_requests(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if not _administrator(request):
        return views.error_page(request, status=403)
    if (set(request.GET) - {"status", "cursor"} or any(len(request.GET.getlist(k)) != 1 for k in request.GET)
            or "status" in request.GET and request.GET["status"] not in STATUSES
            or "cursor" in request.GET and not valid_id(request.GET["cursor"])):
        return views.error_page(request, status=400)
    if request.method == "GET":
        return _list(request)
    operation, target = request.POST.get("operation"), request.POST.get("request_id", "")
    if (operation not in ("review", "decline", "approve-deletion") or not valid_id(target)
            or not _valid_intent(request, operation, target)):
        return views.error_page(request, status=400)
    data = None
    if operation == "decline":
        if request.POST.get("decline_code") not in DECLINE:
            return _list(request, error=REFUSED[400], status=400)
        data = {"decline_code": request.POST["decline_code"]}
    if operation == "approve-deletion" and request.POST.get("confirm") != "yes":
        return _list(request, error="Tick the confirmation to approve the deletion.", status=400)
    code, result = views._api(f"/admin/privacy-requests/{target}/{operation}", method="POST",
                              token=request.gateway_token, **({"data": data} if data else {}))
    if code == 401:
        return views._expired(request)
    expected = {"review": "in_review", "decline": "declined", "approve-deletion": "processing"}[operation]
    if code == 200 and valid_row(result) and result["id"] == target and result["status"] == expected:
        request.session[NOTICE] = {
            "review": "Review opened.", "decline": "Request declined. The account is unchanged.",
            "approve-deletion": ("Deletion approved. The account is deactivated and every session is signed out. "
                                 "Each service erases its own data and confirms; only Engagement, Creators, "
                                 "Moderation and Content take part so far, so the request stays pending.")}[operation]
        return redirect(reverse("privacy-requests"))
    return _list(request, error=_refusal(code, result), status=code if code in (400, 403, 404, 409) else 503)


def _holds(request, account, *, error=None, status=200):
    code, page = views._api(f"/admin/accounts/{account}/holds", token=request.gateway_token, response_limit=131072)
    if code == 401:
        return views._expired(request)
    available = (code == 200 and isinstance(page, dict) and set(page) == {"items"} and isinstance(page["items"], list)
                 and len(page["items"]) <= 50 and all(valid_hold(item) and item["account_id"] == account
                                                      for item in page["items"]))
    rows = ([{**item, "reason_label": HOLD_REASONS[item["reason_code"]],
              "intent": _intent(request, "release", item["id"]) if item["released_at"] is None else None}
             for item in page["items"]] if available else [])
    return views._render(request, "account_holds.html", {
        "title": "Account holds", "account_id": account, "rows": rows, "available": available,
        "reasons": HOLD_REASONS.items(), "place_intent": _intent(request, "place", account),
        "error": error or (None if available else REFUSED[404] if code == 404 else UNAVAILABLE),
        "notice": request.session.pop(NOTICE, None)}, status=404 if code == 404 and status == 200 else status)


@views.privileged
def account_holds(request, target_id):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if not _administrator(request):
        return views.error_page(request, status=403)
    account = str(target_id)
    if request.GET:
        return views.error_page(request, status=400)
    if request.method == "GET":
        return _holds(request, account)
    operation = request.POST.get("operation")
    if operation == "place":
        if not _valid_intent(request, "place", account):
            return views.error_page(request, status=400)
        reason, note = request.POST.get("reason_code"), request.POST.get("note", "").strip()
        if reason not in HOLD_REASONS or not 3 <= len(note) <= 500:
            return _holds(request, account, error="Choose a reason and write a note of 3 to 500 characters.",
                          status=400)
        code, result = views._api(f"/admin/accounts/{account}/holds", method="POST", token=request.gateway_token,
                                  data={"reason_code": reason, "note": note})
        valid = code in (200, 201) and valid_hold(result) and result["account_id"] == account
        notice = "Hold placed. This account's deletion can't be approved until it is released."
    elif operation == "release":
        hold = request.POST.get("hold_id", "")
        if not valid_id(hold) or not _valid_intent(request, "release", hold):
            return views.error_page(request, status=400)
        code, result = views._api(f"/admin/account-holds/{hold}/release", method="POST", token=request.gateway_token)
        valid = (code == 200 and valid_hold(result) and result["id"] == hold and result["account_id"] == account
                 and result["released_at"] is not None)
        notice = "Hold released."
    else:
        return views.error_page(request, status=400)
    if code == 401:
        return views._expired(request)
    if valid:
        request.session[NOTICE] = notice
        return redirect(reverse("account-holds", args=[account]))
    return _holds(request, account, error=_refusal(code, result), status=code if code in (400, 403, 404, 409) else 503)
