"""Server-rendered invitation administration and the private invitee enrollment flow."""

import json
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from cryptography.fernet import InvalidToken
from django.core import signing
from django.http import HttpResponseNotAllowed
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from . import staging_session, views
from .invitation_contracts import identifier, valid_page, valid_receipt, valid_setup, valid_complete

PENDING = "moderator_enrollment"


def intent(request, operation, target):
    return signing.dumps({**views._intent(request, "moderator-invitation-" + operation, target),
                          "key": secrets.token_urlsafe(32)}, salt="moderator-invitations")


@views.privileged
def team(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if set(request.GET) - {"cursor", "sent", "revoked"} or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
        return views.error_page(request, status=400)
    cursor = request.GET.get("cursor")
    if cursor and not identifier(cursor):
        return views.error_page(request, status=400)
    error, result_status = None, 200
    if request.method == "POST":
        operation = request.POST.get("operation")
        target = request.POST.get("id", "new")
        try:
            if operation not in ("create", "revoke") or operation == "revoke" and not identifier(target):
                raise ValueError
            proof = signing.loads(request.POST.get("intent", ""), salt="moderator-invitations", max_age=300)
            key = proof.pop("key")
            if proof != views._intent(request, "moderator-invitation-" + operation, target):
                raise ValueError
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            return views.error_page(request, status=400)
        path = "/admin/moderator-invitations"
        data = {"reason": request.POST.get("reason", "")}
        if operation == "create":
            data.update(email=request.POST.get("email", ""), display_name=request.POST.get("display_name", ""))
        else:
            path += "/" + target + "/revoke"
        result_status, payload = views._api(path, method="POST", data=data, token=request.gateway_token,
                                            idempotency_key=key)
        if result_status == 401:
            return views._expired(request)
        if operation == "create" and result_status == 202:
            if not valid_receipt(payload):
                return views.error_page(request)
            return redirect("/admin/team/?sent=1")
        if operation == "revoke" and result_status == 204:
            return redirect("/admin/team/?revoked=1")
        error = {400: "Check the invitation fields and reason.",
                 403: "An administrator must sign in again with MFA before sending or revoking an invitation.",
                 409: "This invitation conflicts with an existing account, invitation or earlier submission.",
                 429: "The invitation limit has been reached. Try again later."}.get(result_status,
                 "Invitations are unavailable. Try again later.")
    status, page = views._api("/admin/moderator-invitations" + ("?" + urlencode({"cursor": cursor}) if cursor else ""),
                              token=request.gateway_token)
    if status != 200:
        return views._gateway_error(request, status)
    if not valid_page(page) or cursor is not None and page["next_cursor"] == cursor:
        return views.error_page(request)
    items = [{**row, "intent": intent(request, "revoke", row["id"])} for row in page["items"]]
    return views._render(request, "team.html", {"items": items, "intent": intent(request, "create", "new"),
        "next_query": urlencode({"cursor": page["next_cursor"]}) if page["next_cursor"] else None,
        "error": error}, status=result_status if error and result_status in (400, 403, 409, 429) else 503 if error else 200)


def pending(request):
    raw = request.session.get(PENDING)
    try:
        state = json.loads(staging_session._cipher().decrypt(raw.encode()))
        if (set(state) != {"invitation_code", "email", "secret", "expires_at"}
                or not isinstance(state["invitation_code"], str) or len(state["invitation_code"]) != 64
                or not isinstance(state["email"], str)
                or not valid_setup({"secret": state["secret"], "expires_at": state["expires_at"]})
                or not timezone.now() < datetime.fromisoformat(state["expires_at"].replace("Z", "+00:00"))
                <= timezone.now() + timedelta(minutes=5)):
            raise ValueError
        return state
    except (InvalidToken, ValueError, TypeError, AttributeError, KeyError, UnicodeError):
        request.session.pop(PENDING, None)
        return None


@never_cache
@sensitive_post_parameters("invitation_code", "password", "code")
def accept(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    state = pending(request)
    error, status = None, 200
    if request.method == "POST":
        if state is None:
            fields = {name: request.POST.get(name, "") for name in ("invitation_code", "email", "password")}
            status, payload = views._api("/auth/moderator-invitations/setup", method="POST", data=fields)
            if status == 200:
                if not valid_setup(payload):
                    return views.error_page(request)
                staging_session.clear(request)
                state = {"invitation_code": fields["invitation_code"], "email": fields["email"], **payload}
                request.session[PENDING] = staging_session._cipher().encrypt(json.dumps(state).encode()).decode()
                request.session.set_expiry(300)
                rotate_token(request)
                return redirect("moderator-invitation")
        else:
            status, payload = views._api("/auth/moderator-invitations/complete", method="POST", data={
                "invitation_code": state["invitation_code"], "email": state["email"], "code": request.POST.get("code", "")})
            if status == 200:
                staging_session.clear(request)
                rotate_token(request)
                if not valid_complete(payload):
                    return views.error_page(request)
                return render(request, "moderator_invitation.html", {"complete": True,
                               "recovery_codes": payload["recovery_codes"]})
        error = "Enrollment failed. Check the invitation and code, or ask your administrator for help."
    return render(request, "moderator_invitation.html", {"enrollment": state, "error": error},
                  status=status if status in (200, 400, 401, 403, 409, 429) else 503)
