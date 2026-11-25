"""Decision E (D11-008): administrators verify and revoke rights-holder accounts.

Moderation and the Gateway decide who may act (administrator, live MFA, never one's own account). This page
validates their answers, never echoes their error text, and carries a signed, session-bound intent per change.
Verification marks a claimant's later copyright claims for reviewers; it never decides a claim.
"""

from datetime import datetime
from urllib.parse import urlencode

from django.core import signing
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters

from . import account_lookup, views
from .api_contracts import valid_id

SALT = "admin-rights-holders"
NOTICE = "rights_holder_notice"
ROW = {"account_id", "organisation", "evidence", "verified_by", "verified_at", "revoked_at", "active"}
UNAVAILABLE = "Rights holders are unavailable right now. They may not be enabled in this environment."
REFUSED = {400: "Check the organisation (2 to 200 characters) and the evidence note (10 to 2,000 characters).",
           403: "You can't verify or revoke your own account.",
           404: "That rights holder wasn't found.",
           409: "This account is already verified with different details. Revoke it first to change them."}


def _stamp(value):
    try:
        return isinstance(value, str) and len(value) <= 64 and datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def valid_row(item):
    try:
        return (isinstance(item, dict) and set(item) == ROW and valid_id(item["account_id"]) and valid_id(item["verified_by"])
                and isinstance(item["organisation"], str) and 2 <= len(item["organisation"]) <= 200
                and isinstance(item["evidence"], str) and 10 <= len(item["evidence"]) <= 2000
                and _stamp(item["verified_at"]) and type(item["active"]) is bool
                and (item["revoked_at"] is None) == item["active"]
                and (item["revoked_at"] is None or _stamp(item["revoked_at"])))
    except (TypeError, KeyError):
        return False


def valid_page(page, cursor):
    if not isinstance(page, dict) or set(page) != {"items", "next_cursor"} or not isinstance(page["items"], list):
        return False
    if len(page["items"]) > 20 or not all(valid_row(item) for item in page["items"]):
        return False
    ids = [item["account_id"] for item in page["items"]]
    return (ids == sorted(set(ids)) and (cursor is None or all(item > cursor for item in ids))
            and (page["next_cursor"] is None or bool(ids) and page["next_cursor"] == ids[-1]))


def _proof(request, operation, account_id):
    return views._intent(request, "rights-" + operation, account_id)


def _intent(request, operation, account_id):
    return signing.dumps(_proof(request, operation, account_id), salt=SALT)


def _valid_intent(request, operation, account_id):
    try:
        return signing.loads(request.POST.get("intent", ""), salt=SALT, max_age=900) == _proof(request, operation, account_id)
    except (signing.BadSignature, TypeError, ValueError):
        return False


def _page(request, *, candidate=None, error=None, status=200):
    cursor = request.GET.get("cursor")
    code, page = views._api("/admin/rights-holders" + ("?" + urlencode({"cursor": cursor}) if cursor else ""),
                            token=request.gateway_token, response_limit=262144)
    if code == 401:
        return views._expired(request)
    available = code == 200 and valid_page(page, cursor)
    rows = ([{**row, "intent": _intent(request, "revoke", row["account_id"]) if row["active"] else None}
             for row in page["items"]] if available else [])
    return views._render(request, "rights_holders.html", {
        "title": "Rights holders", "rows": rows, "available": available, "candidate": candidate,
        "next_query": urlencode({"cursor": page["next_cursor"]}) if available and page["next_cursor"] else None,
        "error": error or (None if available else UNAVAILABLE), "notice": request.session.pop(NOTICE, None)},
        status=status)


@views.privileged
@sensitive_post_parameters("email")
def rights_holders(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if request.admin_account["roles"] != ["administrator"]:
        return views.error_page(request, status=403)
    if (set(request.GET) - {"cursor"} or any(len(request.GET.getlist(k)) != 1 for k in request.GET)
            or "cursor" in request.GET and not valid_id(request.GET["cursor"])):
        return views.error_page(request, status=400)
    if request.method == "GET":
        return _page(request)
    operation = request.POST.get("operation")
    if operation == "lookup":
        outcome, value, status = account_lookup.find(request, request.POST.get("email", ""), verb="verified")
        if outcome == "expired":
            return views._expired(request)
        if outcome == "found":
            return _page(request, candidate={**value, "intent": _intent(request, "verify", value["account_id"])})
        return _page(request, error=value, status=status)
    account = request.POST.get("account_id", "")
    if operation not in ("verify", "revoke") or not valid_id(account) or not _valid_intent(request, operation, account):
        return views.error_page(request, status=400)
    if operation == "verify":
        organisation, evidence = request.POST.get("organisation", "").strip(), request.POST.get("evidence", "").strip()
        if not 2 <= len(organisation) <= 200 or not 10 <= len(evidence) <= 2000:
            return _page(request, error=REFUSED[400], status=400)
        code, result = views._api("/admin/rights-holders", method="POST", token=request.gateway_token,
                                  data={"account_id": account, "organisation": organisation, "evidence": evidence})
        valid = code in (200, 201) and valid_row(result) and result["account_id"] == account and result["active"]
        notice = ("Verified. This account's new copyright claims are marked for reviewers." if code == 201
                  else "This account was already verified with these details.")
    else:
        code, result = views._api(f"/admin/rights-holders/{account}/revoke", method="POST", token=request.gateway_token)
        valid = code == 200 and valid_row(result) and result["account_id"] == account and not result["active"]
        notice = "Verification revoked. Claims already made keep the status they had."
    if code == 401:
        return views._expired(request)
    if valid:
        request.session[NOTICE] = notice
        return redirect(reverse("rights-holders"))
    if code in REFUSED:
        return _page(request, error=REFUSED[code], status=code)
    return _page(request, error=UNAVAILABLE, status=503)
