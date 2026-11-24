"""Administrator console for creator onboarding: find an account, invite it, review applications.

Everything is decided by the existing Identity, Creators and Gateway services; this module only
presents their answers and carries a signed, session-bound intent for each mutation.
"""

from urllib.parse import urlencode

from django.core import signing
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters

from . import views
from .admin_contracts import (valid_candidate, valid_creator_summary, valid_outstanding_invitations,
                             valid_pending_applications)
from .api_contracts import valid_id

SALT = "admin-creators"
NOTICE = "creator_notice"
UNAVAILABLE = "Creator onboarding is unavailable right now. It may not be enabled in this environment."


def _proof(request, operation, account_id):
    return views._intent(request, "creator-" + operation, account_id)


def _intent(request, operation, account_id):
    return signing.dumps(_proof(request, operation, account_id), salt=SALT)


def _valid_intent(request, operation, account_id):
    try:
        return signing.loads(request.POST.get("intent", ""), salt=SALT, max_age=900) == _proof(request, operation, account_id)
    except (signing.BadSignature, TypeError, ValueError):
        return False


def _outstanding(request):
    """Invited-but-not-applied accounts, with a signed revoke intent each. Unavailable never hides the rest of the page."""
    cursor = request.GET.get("invited")
    code, page = views._api("/creator-invitations" + ("?" + urlencode({"cursor": cursor}) if cursor else ""),
                            token=request.gateway_token)
    if code == 401:
        return None
    available = (code == 200 and valid_outstanding_invitations(page, cursor)
                 and (page["next_cursor"] is None or page["next_cursor"] != cursor))
    rows = [{**row, "intent": _intent(request, "revoke", row["account_id"])} for row in page["items"]] if available else []
    return {"available": available, "rows": rows,
            "next_query": urlencode({"invited": page["next_cursor"]}) if available and page["next_cursor"] else None}


def _page(request, *, candidate=None, error=None, status=200):
    cursor = request.GET.get("cursor")
    query = "?" + urlencode({"cursor": cursor}) if cursor else ""
    code, page = views._api("/creator-applications" + query, token=request.gateway_token)
    if code == 401:
        return views._expired(request)
    invitations = _outstanding(request)
    if invitations is None:
        return views._expired(request)
    available = (code == 200 and valid_pending_applications(page, cursor)
                 and (page["next_cursor"] is None or page["next_cursor"] != cursor))
    applications = [{**row, "intent": _intent(request, "decision", row["account_id"])} for row in page["items"]] if available else []
    return views._render(request, "creators.html", {
        "applications": applications, "applications_available": available,
        "next_query": urlencode({"cursor": page["next_cursor"]}) if available and page["next_cursor"] else None,
        "invitations": invitations, "candidate": candidate, "error": error, "notice": request.session.pop(NOTICE, None)}, status=status)


@views.privileged
@sensitive_post_parameters("email")
def creators(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if request.admin_account["roles"] != ["administrator"]:
        return views.error_page(request, status=403)
    if set(request.GET) - {"cursor", "invited"} or any(len(request.GET.getlist(k)) != 1 for k in request.GET) \
            or any(k in request.GET and not valid_id(request.GET[k]) for k in ("cursor", "invited")):
        return views.error_page(request, status=400)
    if request.method == "GET":
        return _page(request)
    operation = request.POST.get("operation")
    if operation == "lookup":
        return _lookup(request)
    if operation == "invite":
        return _invite(request)
    if operation == "decide":
        return _decide(request)
    if operation == "revoke":
        return _revoke(request)
    return views.error_page(request, status=400)


def _lookup(request):
    email = request.POST.get("email", "").strip()
    if not 3 <= len(email) <= 254 or "@" not in email:
        return _page(request, error="Enter the person's full email address.", status=400)
    code, found = views._api("/admin/accounts/lookup", method="POST", data={"email": email}, token=request.gateway_token)
    if code == 401:
        return views._expired(request)
    if code == 200 and valid_candidate(found):
        return _page(request, candidate={**found, "intent": _intent(request, "invite", found["account_id"])})
    message = {404: "No account with that email can be invited. The person must register in the app first.",
               429: "Too many lookups. Try again later.",
               403: "Only administrators can look up accounts.",
               400: "Enter the person's full email address."}.get(code, "Account lookup is unavailable right now.")
    return _page(request, error=message, status=code if code in (400, 403, 404, 429) else 503)


def _invite(request):
    account = request.POST.get("account_id", "")
    if not valid_id(account) or not _valid_intent(request, "invite", account):
        return views.error_page(request, status=400)
    code, result = views._api("/creator-invitations", method="POST", data={"account_id": account}, token=request.gateway_token)
    if code == 401:
        return views._expired(request)
    if code in (200, 201) and valid_creator_summary(result, account):
        request.session[NOTICE] = (
            "Invitation recorded. The person can now apply from the app's Become a creator screen." if code == 201
            else f"This account was already invited (status: {result['status']}).")
        return redirect(reverse("creators"))
    return _page(request, error="You can't invite your own account." if code == 403 else UNAVAILABLE,
                 status=403 if code == 403 else 503)


def _decide(request):
    account, decision = request.POST.get("account_id", ""), request.POST.get("decision")
    if not valid_id(account) or decision not in ("approved", "rejected") or not _valid_intent(request, "decision", account):
        return views.error_page(request, status=400)
    handle = request.POST.get("handle", "")
    if request.POST.get("confirmed") != "1":
        return views._render(request, "creator_confirm.html", {
            "title": "Confirm your decision", "account_id": account, "decision": decision, "handle": handle[:30],
            "intent": request.POST["intent"]})
    code, result = views._api(f"/creator-applications/{account}/decision", method="POST",
                              data={"decision": decision}, token=request.gateway_token)
    if code == 401:
        return views._expired(request)
    if code == 200 and valid_creator_summary(result, account) and result["status"] == decision:
        request.session[NOTICE] = ("Application approved. The account becomes a creator." if decision == "approved"
                                   else "Application rejected.")
        return redirect(reverse("creators"))
    if code in (403, 404, 409):
        return _page(request, error={403: "You can't review your own application.", 404: "That application no longer exists.",
                                     409: "That application has already been decided."}[code], status=code)
    return _page(request, error=UNAVAILABLE, status=503)


def _revoke(request):
    account = request.POST.get("account_id", "")
    if not valid_id(account) or not _valid_intent(request, "revoke", account):
        return views.error_page(request, status=400)
    if request.POST.get("confirmed") != "1":
        return views._render(request, "creator_revoke_confirm.html", {
            "account_id": account, "intent": request.POST["intent"]})
    code, result = views._api(f"/creator-invitations/{account}/revoke", method="POST", data={},
                              token=request.gateway_token)
    if code == 401:
        return views._expired(request)
    if code == 200 and valid_creator_summary(result, account) and result["status"] == "revoked":
        request.session[NOTICE] = "Invitation revoked. The person can no longer apply until you invite them again."
        return redirect(reverse("creators"))
    if code in (403, 404, 409):
        return _page(request, error={403: "Only administrators can revoke an invitation, and not their own.",
                                     404: "That invitation no longer exists.",
                                     409: "That person has already applied, so the invitation can't be revoked. Review the application instead."}[code],
                     status=code)
    return _page(request, error=UNAVAILABLE, status=503)
