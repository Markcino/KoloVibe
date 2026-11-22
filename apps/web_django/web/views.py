"""Server-rendered, MFA-gated R1 administration console."""

import json
import re
import secrets
import ssl
from datetime import datetime, timezone
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from django.conf import settings
from django.core import signing
from django.http import FileResponse, Http404, HttpResponseNotAllowed, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.middleware.csrf import rotate_token
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST
from django.utils.crypto import salted_hmac

from .api_contracts import valid_id, valid_queue_page, valid_sessions, valid_decision, QUEUE_STATUS, ACTIONS
from . import staging_session
from .admin_contracts import STATUSES


STATIC_ASSETS = {
    "css/site.css": "text/css; charset=utf-8",
    "images/logo.svg": "image/svg+xml",
    "images/landscape_logo_with_name.svg": "image/svg+xml",
    "images/portrait_logo_with_name.svg": "image/svg+xml",
}


@require_GET
def static_asset(request, asset):
    content_type = STATIC_ASSETS.get(asset)
    if content_type is None:
        raise Http404
    response = FileResponse((settings.BASE_DIR / "static" / asset).open("rb"),
                            content_type=content_type)
    response["Cache-Control"] = "public, max-age=3600"
    return response


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _api(path, *, method="GET", data=None, token=None, idempotency_key=None, binary=False, response_limit=65536):
    headers = {"Accept": "application/json"}
    if settings.GATEWAY_HOST:
        headers["Host"] = settings.GATEWAY_HOST
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    body = None
    if data is not None:
        body = json.dumps(data, separators=(",", ":")).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(settings.GATEWAY_URL.rstrip("/") + "/api/v1" + path,
                      data=body, headers=headers, method=method)
    try:
        context = (ssl.create_default_context(cafile=settings.GATEWAY_CA)
                   if settings.ENVIRONMENT == "staging" else None)
        handlers = [ProxyHandler({}), _NoRedirect()]
        if context is not None:
            handlers.append(HTTPSHandler(context=context))
        with build_opener(*handlers).open(request, timeout=15 if binary else 5) as response:
            status = response.status
            limit = 50 * 1024 * 1024 if binary and status == 200 else response_limit
            raw = response.read(limit + 1)
            if binary and status == 200:
                if response.headers.get("Content-Type") != "video/mp4" or not 0 < len(raw) <= limit:
                    return 503, {}
                return 200, raw
    except HTTPError as error:
        status, raw = error.code, error.read(65537)
    except (URLError, OSError, TimeoutError):
        return 503, {"detail": "Service unavailable"}
    if len(raw) > response_limit:
        return 503, {"detail": "Service unavailable"}
    try:
        payload = json.loads(raw) if raw else {}
        if not isinstance(payload, dict):
            raise ValueError("Invalid response")
    except (ValueError, UnicodeError):
        return 503, {"detail": "Service unavailable"}
    return status, payload


@never_cache
def error_page(request, exception=None, status=503):
    # One non-enumerating message. Never render gateway response bodies.
    return render(request, "status.html", {
        "title": "Request unavailable",
        "message": "This request cannot be completed. Sign in again or return to the dashboard.",
    }, status=status)


def error_400(request, exception=None):
    return error_page(request, status=400)


def error_403(request, exception=None, reason=None):
    return error_page(request, status=403)


def error_404(request, exception=None):
    return error_page(request, status=404)


def error_500(request):
    return error_page(request, status=500)


def _clear_credentials(response, request):
    staging_session.clear(request)
    response["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    # Remove legacy local cookie fixtures when a browser is signed out.
    for name in ("kv_access", "kv_refresh"):
        if name in request.COOKIES:
            response.delete_cookie(name, samesite="Strict")


def _expired(request):
    response = redirect("/login/?expired=1")
    _clear_credentials(response, request)
    return response


def privileged(view):
    @never_cache
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.session.get("authenticated"):
            return redirect("login")
        status, account, token = staging_session.authenticated(request, _api)
        if status == 401:
            return _expired(request)
        if status != 200:
            if status == 403:
                response = error_page(request, status=403)
                _clear_credentials(response, request)
                return response
            if view.__name__ == "logout" and request.method == "POST":
                return _finish_logout(request)
            return error_page(request)
        if not staging_session.privileged_account(account):
            return error_page(request, status=403)
        if request.session.get("mfa_verified") is not True:
            return _expired(request)
        request.admin_account, request.gateway_token = account, token
        return view(request, *args, **kwargs)
    return guarded


def _crumbs(request):
    match = request.resolver_match
    name = match.url_name if match else ""
    home = ("Dashboard", reverse("dashboard"))
    kind = (match.kwargs if match else {}).get("kind")
    if kind and name.endswith("-detail"):
        return [home, (kind.title(), reverse(f"moderation-{kind}")), ("Review", None)]
    if kind:
        return [home, (kind.title(), None)]
    if name in ("points", "audit", "account"):
        return [home, (name.title(), None)]
    sub = {"profile-edit": "Edit profile", "password-change": "Change password", "sessions": "Active sessions"}
    if name in sub:
        return [home, ("Account", reverse("account")), (sub[name], None)]
    return []


def _flash(request, text, level="success"):
    request.session["flash"] = [level, text]


def _render(request, template, context=None, *, status=200):
    roles = request.admin_account["roles"]
    flash = request.session.pop("flash", None)
    return render(request, template, {
        "account": request.admin_account,
        "role": roles[0],
        "can_review_points": "administrator" in roles,
        "crumbs": _crumbs(request),
        "flash": [flash[0], flash[1], "check" if flash[0] == "success" else "warning"] if flash else None,
        **(context or {}),
    }, status=status)


def _gateway_error(request, status):
    if status == 401:
        return _expired(request)
    return error_page(request, status=status if status in (400, 403, 404, 409, 429) else 503)


@require_GET
def root(request):
    return redirect("login")


@never_cache
@sensitive_post_parameters("password")
def login(request):
    if request.method == "GET":
        return render(request, "form.html", {"title": "Sign in", "kind": "login"})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    if (staging_session.MFA_PENDING in request.session
            or request.session.get("authenticated")):
        staging_session.clear(request)
    status, payload = _api("/auth/login", method="POST", data={
        "email": request.POST.get("email", ""), "password": request.POST.get("password", "")})
    if status == 202:
        if staging_session.begin_mfa(request, payload, request.POST.get("email", "")):
            return redirect("login-mfa")
        status, payload = 503, {"detail": "Sign in unavailable"}
    if status == 200:
        # Password-only sessions never enter the console. Revoke any issued tokens.
        refresh = payload.get("refresh_token")
        if isinstance(refresh, str) and refresh:
            _api("/auth/logout", method="POST", data={"refresh_token": refresh})
        return error_page(request, status=403)
    return render(request, "form.html", {"title": "Sign in", "kind": "login",
                                          "error": "Sign in failed. Check your credentials or try again later."},
                  status=status if status in (401, 403, 429) else 503)


@never_cache
@sensitive_post_parameters("code")
def login_mfa(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    pending = staging_session.pending_mfa(request)
    if pending is None:
        return redirect("login")
    if request.method == "GET":
        return render(request, "form.html", {"title": "Verify your sign-in", "kind": "mfa"})
    code = request.POST.get("code", "")
    if re.fullmatch(r"(?:[0-9]{6}|[A-Za-z0-9_-]{32,128})", code) is None:
        return render(request, "form.html", {"title": "Verify your sign-in", "kind": "mfa",
                      "error": "Enter an authenticator code or recovery code."}, status=400)
    status, payload = _api("/auth/mfa/verify", method="POST", data={
        "challenge_token": pending["challenge_token"], "code": code})
    if status == 200:
        # Flush before validating the response: Django does not save session
        # mutations on 5xx responses, so pop() alone would leave a stale challenge.
        staging_session.clear(request)
        account = payload.get("user")
        if (staging_session.privileged_account(account)
                and isinstance(account.get("email"), str)
                and account["email"].strip().casefold() == pending["email"]
                and staging_session.start(request, payload, mfa_verified=True)):
            rotate_token(request)
            return redirect("dashboard")
        # Do not keep an issued Identity session after rejecting its response.
        refresh = payload.get("refresh_token")
        if isinstance(refresh, str) and refresh:
            _api("/auth/logout", method="POST", data={"refresh_token": refresh})
        return render(request, "status.html", {"title": "Sign in unavailable"}, status=503)
    if status == 429:
        request.session.pop(staging_session.MFA_PENDING, None)
    return render(request, "form.html", {"title": "Verify your sign-in", "kind": "mfa",
                  "error": "Verification failed. Try again or restart sign in."},
                  status=status if status in (400, 401, 403, 429) else 503)


@require_GET
def add_trailing_slash(request):
    query = request.META.get("QUERY_STRING", "")
    return redirect("/" + request.path.lstrip("/") + "/" + ("?" + query if query else ""))


@privileged
@require_GET
def dashboard(request):
    from .admin_contracts import valid_totals, valid_holds
    status, totals = _api("/moderation/totals", token=request.gateway_token)
    if status != 200:
        return _gateway_error(request, status)
    if not valid_totals(totals):
        return error_page(request)
    status, holds = _api("/engagement/fraud-holds", token=request.gateway_token)
    if status != 200:
        return _gateway_error(request, status)
    if not valid_holds(holds):
        return error_page(request)
    from .admin_contracts import valid_audit_page
    audit_status, events = _api("/admin/audit", token=request.gateway_token)
    if audit_status == 401:
        return _expired(request)
    recent = events["items"] if audit_status == 200 and valid_audit_page(events) else None
    attention = totals["videos"]["review"] + totals["reports"]["open"] + totals["appeals"]["open"]
    return _render(request, "dashboard.html", {"totals": totals, "holds": holds, "recent_events": recent, "attention": attention})


def _queue_query(request, kind):
    if (set(request.GET) - {"cursor", "status"}
            or any(len(request.GET.getlist(key)) != 1 for key in request.GET)):
        return None
    cursor, status = request.GET.get("cursor"), request.GET.get("status", QUEUE_STATUS[kind])
    from .admin_contracts import STATUSES
    if cursor is not None and not valid_id(cursor) or status not in STATUSES[kind]:
        return None
    return cursor, status


def _queue_page(request, kind, cursor, selected_status=None):
    values = {}
    if cursor:
        values["cursor"] = cursor
    if selected_status and selected_status != QUEUE_STATUS[kind]:
        values["status"] = selected_status
    query = "?" + urlencode(values) if values else ""
    status, page = _api("/moderation/" + kind + query, token=request.gateway_token, response_limit=524288)
    if status == 200 and not valid_queue_page(page, kind, cursor=cursor, selected_status=selected_status):
        return 503, {}
    return status, page


def _unavailable(request, title, message):
    return _render(request, "unavailable.html", {"title": title, "message": message})


@privileged
@require_GET
def moderation_queue(request, kind):
    query = _queue_query(request, kind)
    if query is None:
        return error_page(request, status=400)
    cursor, selected_status = query
    status, page = _queue_page(request, kind, cursor, selected_status)
    if status != 200:
        return _gateway_error(request, status)
    next_query = urlencode({"cursor": page["next_cursor"], "status": selected_status}) if page["next_cursor"] else None
    return _render(request, "moderation_list.html", {
        "title": kind.title(), "kind": kind, "items": page["items"],
        "selected_status": selected_status, "next_query": next_query,
        "statuses": STATUSES[kind],
        "default_status": QUEUE_STATUS[kind],
        "count": len(page["items"]), "has_more": bool(page["next_cursor"]),
        "detail_query": "?" + urlencode({"cursor": cursor}) if cursor else "",
    })


DESTRUCTIVE_ACTIONS = {"reject", "remove", "deny"}


def _intent(request, kind, target_id):
    return {"kind": kind, "target": str(target_id), "actor": request.admin_account["id"],
            "session": salted_hmac("admin-decision-session", request.session.session_key).hexdigest()}


@privileged
def moderation_detail(request, kind, target_id):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if _queue_query(request, kind) is None:
        return error_page(request, status=400)
    if request.method == "POST":
        try:
            intent = signing.loads(request.POST.get("intent", ""), salt="admin-decision", max_age=900)
            key = intent.pop("key")
            video_id = intent.pop("video")
            if not valid_id(video_id) or intent != _intent(request, kind, target_id) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError, AttributeError, KeyError):
            return error_page(request, status=400)
        action, reason = request.POST.get("action", ""), request.POST.get("reason", "")
        if action not in ACTIONS[kind] or not 10 <= len(reason.strip()) <= len(reason) <= 2000:
            return error_page(request, status=400)
        if action in DESTRUCTIVE_ACTIONS and request.POST.get("confirm") != "1":
            return _render(request, "decision_confirm.html", {
                "title": "Confirm decision", "kind": kind, "action": action, "reason": reason.strip(),
                "intent": request.POST["intent"], "item_id": str(target_id),
                "back_url": reverse(f"moderation-{kind}-detail", args=[target_id])})
        status, result = _api(f"/moderation/{kind}/{target_id}/decisions", method="POST",
                              token=request.gateway_token, data={"action": action, "reason": reason.strip()},
                              idempotency_key=key)
        if status not in (200, 201):
            return _gateway_error(request, status)
        if not valid_decision(result, video_id, action):
            return error_page(request)
        return _render(request, "decision_result.html", {"kind": kind, "action": action, "item_id": str(target_id),
                                                          "queue_url": reverse(f"moderation-{kind}")})
    status, detail = _api(f"/moderation/{kind}/{target_id}", token=request.gateway_token, response_limit=524288)
    if status != 200:
        return _gateway_error(request, status)
    from .reviewer_contracts import valid_detail
    if not valid_detail(detail) or detail["record"]["id"] != str(target_id):
        return error_page(request)
    item = detail["record"]
    intent = signing.dumps({**_intent(request, kind, target_id), "key": secrets.token_urlsafe(32),
                            "video": item["id"] if kind == "videos" else item["video_id"]},
                           salt="admin-decision")
    return _render(request, "moderation_detail.html", {
        "title": kind.title() + " review", "kind": kind, "item": item,
        "actions": sorted(ACTIONS[kind]), "intent": intent, "detail": detail,
    })


@privileged
@require_GET
def points(request):
    from .admin_contracts import valid_points_review
    if (set(request.GET) - {"account", "cursor", "status", "as_of"}
            or any(len(request.GET.getlist(key)) != 1 or len(request.GET[key]) > 100 for key in request.GET)):
        return error_page(request, status=400)
    values = dict(request.GET.items())
    account = values.pop("account", None)
    if (account is not None and not valid_id(account) or "cursor" in values and not valid_id(values["cursor"])
            or not account and "status" in values):
        return error_page(request, status=400)
    endpoint = f"/admin/points/accounts/{account}" if account else "/admin/points/balances"
    query = "?" + urlencode(values) if values else ""
    status, page = _api(endpoint + query, token=request.gateway_token)
    if status != 200:
        return _gateway_error(request, status)
    if (not valid_points_review(page) or account and page.get("account_id") != account
            or page["next_cursor"] is not None and page["next_cursor"] == values.get("cursor")):
        return error_page(request)
    params = {**values, "as_of": page["as_of"], **({"account": account} if account else {})}
    next_query = urlencode({**params, "cursor": page["next_cursor"]}) if page["next_cursor"] else None
    return _render(request, "points_review.html", {"page": page, "selected_account": account, "next_query": next_query,
        "statuses": ["all", "awards", "reversals", "adjustments"], "selected_status": values.get("status", "all")})


def _audit_bound(raw):
    """Return the gateway value and the datetime-local display value; naive input is UTC."""
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw, ""
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), stamp.strftime("%Y-%m-%dT%H:%M")


@privileged
@require_GET
def audit(request):
    from .admin_contracts import valid_audit_page
    if (set(request.GET) - {"cursor", "kind", "producer", "since", "until"}
            or any(len(request.GET.getlist(key)) != 1 or len(request.GET[key]) > 100 for key in request.GET)):
        return error_page(request, status=400)
    values = dict(request.GET.items())
    if "cursor" in values and not valid_id(values["cursor"]):
        return error_page(request, status=400)
    display = dict(values)
    for key in ("since", "until"):
        if key in values:
            values[key], display[key] = _audit_bound(values[key])
    query = "?" + urlencode(values) if values else ""
    status, page = _api("/admin/audit" + query, token=request.gateway_token)
    if status != 200:
        return _gateway_error(request, status)
    if not valid_audit_page(page) or page["next_cursor"] is not None and page["next_cursor"] == values.get("cursor"):
        return error_page(request)
    next_query = urlencode({**values, "cursor": page["next_cursor"]}) if page["next_cursor"] else None
    return _render(request, "audit.html", {"items": page["items"], "next_query": next_query, "filters": display, "producers": ["identity", "moderation", "creators", "content", "points", "audit"]})


@privileged
@require_GET
def account(request):
    return _render(request, "account.html")


@privileged
@sensitive_post_parameters("current_password", "new_password")
def password_change(request):
    if request.method == "GET":
        return _render(request, "account_form.html", {"title": "Change password", "kind": "change_password"})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    status, _ = _api("/me/password", method="PATCH", token=request.gateway_token, data={
        "current_password": request.POST.get("current_password", ""),
        "new_password": request.POST.get("new_password", ""),
    })
    if status == 204:
        response = redirect("login")
        _clear_credentials(response, request)
        return response
    return _gateway_error(request, status)


@privileged
def profile_edit(request):
    if request.method == "GET":
        return _render(request, "account_form.html", {"title": "Edit profile", "kind": "profile"})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    status, payload = _api("/me", method="PATCH", token=request.gateway_token,
                           data={"display_name": request.POST.get("display_name", "")})
    if status == 200 and payload.get("id") == request.admin_account["id"]:
        _flash(request, "Profile updated.")
        return redirect("account")
    return _gateway_error(request, status)


@privileged
@require_GET
def sessions(request):
    status, payload = _api("/me/sessions", token=request.gateway_token)
    if status == 200 and valid_sessions(payload):
        return _render(request, "sessions.html", {"items": payload["items"]})
    return _gateway_error(request, status)


@privileged
@require_POST
def revoke_session(request, session_id):
    status, _ = _api("/me/sessions/" + str(session_id), method="DELETE", token=request.gateway_token)
    if status == 204:
        _flash(request, "Session ended.")
        return redirect("sessions")
    return _gateway_error(request, status)


@privileged
@require_POST
def logout(request):
    return _finish_logout(request)


def _finish_logout(request):
    refresh = staging_session.refresh_for_logout(request)
    confirmed = False
    if refresh:
        status, _ = _api("/auth/logout", method="POST", data={"refresh_token": refresh})
        confirmed = status == 204
    response = redirect("login") if confirmed else render(request, "status.html", {
        "title": "Signed out on this browser.",
        "message": "Server session revocation could not be confirmed.",
    }, status=503)
    _clear_credentials(response, request)
    return response


@privileged
@require_GET
def reviewer_preview(request, preview_id):
    if request.GET:
        return error_page(request, status=400)
    status, payload = _api(f"/moderation/previews/{preview_id}", token=request.gateway_token, binary=True)
    if status != 200:
        return _gateway_error(request, status)
    response = HttpResponse(payload, content_type="video/mp4")
    response["Content-Disposition"] = 'inline; filename="review-preview.mp4"'
    response["Referrer-Policy"] = "no-referrer"
    return response
