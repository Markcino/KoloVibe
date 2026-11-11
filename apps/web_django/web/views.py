"""Server-rendered R1 web client. All records come from the public gateway."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .api_contracts import valid_creator, valid_id, valid_page, valid_video, valid_points_balance, valid_points_page

ACCESS_COOKIE = "kv_access"
REFRESH_COOKIE = "kv_refresh"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _api(path, *, method="GET", data=None, token=None):
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data, separators=(",", ":")).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(settings.GATEWAY_URL.rstrip("/") + "/api/v1" + path,
                      data=body, headers=headers, method=method)
    try:
        with build_opener(_NoRedirect()).open(request, timeout=5) as response:
            status, raw = response.status, response.read(65537)
    except HTTPError as error:
        status, raw = error.code, error.read(65537)
    except (URLError, OSError, TimeoutError):
        return 503, {"detail": "Service unavailable"}
    if len(raw) > 65536:
        return 503, {"detail": "Service unavailable"}
    try:
        payload = json.loads(raw) if raw else {}
        if not isinstance(payload, dict):
            raise ValueError("Invalid response")
    except (ValueError, UnicodeError):
        return 503, {"detail": "Service unavailable"}
    return status, payload


def _set_credentials(response, payload):
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
        return False
    common = {"httponly": True, "samesite": "Strict", "secure": False}
    response.set_cookie(ACCESS_COOKIE, access, max_age=300, **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=30 * 24 * 3600, **common)
    return True


def _clear_credentials(response):
    response.delete_cookie(ACCESS_COOKIE, samesite="Strict")
    response.delete_cookie(REFRESH_COOKIE, samesite="Strict")


def _own_account(request):
    access = request.COOKIES.get(ACCESS_COOKIE)
    if access:
        status, payload = _api("/me", token=access)
        if status == 200:
            return status, payload, None
        if status != 401:
            return status, {}, None
    refresh = request.COOKIES.get(REFRESH_COOKIE)
    if not refresh:
        return 401, {}, None
    status, rotated = _api("/auth/refresh", method="POST", data={"refresh_token": refresh})
    if status != 200:
        return status, {}, None
    if not all(isinstance(rotated.get(key), str) and rotated[key]
               for key in ("access_token", "refresh_token")):
        return 503, {}, None
    status, account = _api("/me", token=rotated.get("access_token"))
    return status, account, rotated


@require_GET
def feed(request):
    filters = {key: request.GET[key] for key in request.GET}
    if (set(filters) - {"cursor", "creator_id"}
            or any(len(request.GET.getlist(key)) != 1 or not valid_id(value)
                   for key, value in filters.items())):
        return render(request, "status.html", {"title": "Invalid video query."}, status=400)
    status, payload = _api("/videos" + ("?" + urlencode(filters) if filters else ""))
    if status == 200 and not valid_page(payload, **filters):
        status = 503
    if status == 400:
        return render(request, "status.html", {
            "title": "This video page is no longer available. Return to Explore to start again.",
        }, status=400)
    items = payload.get("items", []) if status == 200 else []
    next_query = None
    if status == 200 and payload["next_cursor"]:
        next_query = urlencode({**filters, "cursor": payload["next_cursor"]})
    return render(request, "feed.html", {"items": items, "unavailable": status != 200,
                                       "next_query": next_query},
                  status=200 if status == 200 else 503)


@require_GET
def video(request, video_id):
    status, payload = _api("/videos/" + str(video_id))
    if status == 200 and (not valid_video(payload) or payload["id"] != str(video_id)):
        status = 503
    return render(request, "video.html", {"video": payload if status == 200 else None,
                                          "unavailable": status == 503},
                  status=status if status in (200, 404, 503) else 503)


@require_GET
def creator_detail(request, creator_id):
    status, payload = _api("/creators/" + str(creator_id))
    if status == 200 and (not valid_creator(payload) or payload["id"] != str(creator_id)):
        status = 503
    return render(request, "creator.html", {"creator": payload if status == 200 else None,
                                            "unavailable": status == 503},
                  status=status if status in (200, 404, 503) else 503)


def register(request):
    if request.method == "GET":
        return render(request, "form.html", {"title": "Create an account", "kind": "register"})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    status, payload = _api("/auth/register", method="POST", data={
        "email": request.POST.get("email", ""),
        "display_name": request.POST.get("display_name", ""),
        "password": request.POST.get("password", ""),
    })
    if status == 201:
        return redirect("verify")
    return render(request, "form.html", {"title": "Create an account", "kind": "register",
                                          "error": payload.get("detail", "Registration unavailable")},
                  status=400 if status in (400, 409) else 503)


def verify(request):
    if request.method == "GET":
        return render(request, "form.html", {"title": "Verify your email", "kind": "verify"})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    status, payload = _api("/auth/verify", method="POST", data={"code": request.POST.get("code", "")})
    if status == 200:
        return redirect("login")
    return render(request, "form.html", {"title": "Verify your email", "kind": "verify",
                                          "error": payload.get("detail", "Verification unavailable")},
                  status=400 if status == 400 else 503)


def password_reset_request(request):
    if request.method == "GET":
        return render(request, "form.html", {"title": "Reset your password", "kind": "reset_request"})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    status, payload = _api("/auth/password/reset-request", method="POST",
                           data={"email": request.POST.get("email", "")})
    if status == 204:
        return render(request, "status.html", {
            "title": "If your account is eligible, check your email for a reset code."
        })
    return render(request, "form.html", {"title": "Reset your password", "kind": "reset_request",
                                          "error": payload.get("detail", "Password reset unavailable")},
                  status=400 if status == 400 else 503)


def password_reset(request):
    if request.method == "GET":
        return render(request, "form.html", {"title": "Enter your reset code", "kind": "reset"})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    status, payload = _api("/auth/password/reset", method="POST", data={
        "code": request.POST.get("code", ""),
        "new_password": request.POST.get("new_password", ""),
    })
    if status == 204:
        response = redirect("login")
        _clear_credentials(response)
        return response
    return render(request, "form.html", {"title": "Enter your reset code", "kind": "reset",
                                          "error": payload.get("detail", "Password reset unavailable")},
                  status=400 if status == 400 else 503)


def login(request):
    if request.method == "GET":
        return render(request, "form.html", {"title": "Sign in", "kind": "login"})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    status, payload = _api("/auth/login", method="POST", data={
        "email": request.POST.get("email", ""), "password": request.POST.get("password", "")})
    if status == 200:
        response = redirect("account")
        if _set_credentials(response, payload):
            return response
        status, payload = 503, {"detail": "Sign in unavailable"}
    return render(request, "form.html", {"title": "Sign in", "kind": "login",
                                          "error": payload.get("detail", "Sign in unavailable")},
                  status=status if status in (401, 403, 429) else 503)


@require_GET
def account(request):
    status, payload, rotated = _own_account(request)
    if status != 200:
        response = redirect("login") if status == 401 else render(request, "status.html",
                        {"title": "Account unavailable"}, status=503)
        if status == 401:
            _clear_credentials(response)
        elif rotated:
            _set_credentials(response, rotated)
        return response
    response = render(request, "account.html", {"account": payload})
    if rotated:
        _set_credentials(response, rotated)
    return response


def _account_access(request):
    status, account_data, rotated = _own_account(request)
    if status == 200:
        token = rotated["access_token"] if rotated else request.COOKIES.get(ACCESS_COOKIE)
        return account_data, token, rotated, None
    response = redirect("login") if status == 401 else render(
        request, "status.html", {"title": "Account unavailable"}, status=503)
    if status == 401:
        _clear_credentials(response)
    elif rotated:
        _set_credentials(response, rotated)
    return None, None, None, response


def profile_edit(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    account_data, token, rotated, blocked = _account_access(request)
    if blocked is not None:
        return blocked
    if request.method == "GET":
        response = render(request, "form.html", {
            "title": "Edit profile", "kind": "profile", "account": account_data,
        })
    else:
        status, payload = _api("/me", method="PATCH", token=token,
                               data={"display_name": request.POST.get("display_name", "")})
        if status == 200 and payload.get("id") == account_data.get("id"):
            response = redirect("account")
        else:
            response = render(request, "form.html", {
                "title": "Edit profile", "kind": "profile", "account": account_data,
                "error": payload.get("detail", "Profile update unavailable"),
            }, status=400 if status == 400 else 503)
    if rotated:
        _set_credentials(response, rotated)
    return response


def password_change(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    account_data, token, rotated, blocked = _account_access(request)
    if blocked is not None:
        return blocked
    if request.method == "GET":
        response = render(request, "form.html", {"title": "Change password", "kind": "change_password"})
    else:
        status, payload = _api("/me/password", method="PATCH", token=token, data={
            "current_password": request.POST.get("current_password", ""),
            "new_password": request.POST.get("new_password", ""),
        })
        if status == 204:
            response = redirect("login")
            _clear_credentials(response)
            return response
        response = render(request, "form.html", {
            "title": "Change password", "kind": "change_password",
            "error": payload.get("detail", "Password change unavailable"),
        }, status=400 if status == 400 else 401 if status == 401 else 503)
    if rotated:
        _set_credentials(response, rotated)
    return response


@require_GET
def sessions(request):
    account_data, token, rotated, blocked = _account_access(request)
    if blocked is not None:
        return blocked
    status, payload = _api("/me/sessions", token=token)
    items = payload.get("items")
    if status == 200 and (not isinstance(items, list) or len(items) > 40 or any(
            not isinstance(item, dict) or set(item) != {"id", "created_at", "expires_at", "current"}
            or not valid_id(item["id"]) or not isinstance(item["current"], bool)
            or not all(isinstance(item[key], str) for key in ("created_at", "expires_at"))
            for item in items)):
        status = 503
    if status == 200:
        response = render(request, "sessions.html", {"items": items})
    else:
        response = render(request, "status.html", {"title": "Sessions unavailable"}, status=503)
    if rotated:
        _set_credentials(response, rotated)
    return response


@require_POST
def revoke_session(request, session_id):
    account_data, token, rotated, blocked = _account_access(request)
    if blocked is not None:
        return blocked
    status, payload = _api("/me/sessions/" + str(session_id), method="DELETE", token=token)
    if status == 204:
        response = redirect("sessions")
    else:
        response = render(request, "status.html", {
            "title": payload.get("detail", "Session could not be ended"),
        }, status=409 if status == 409 else 404 if status == 404 else 503)
    if rotated:
        _set_credentials(response, rotated)
    return response


def preferences(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    account_data, token, rotated, blocked = _account_access(request)
    if blocked is not None:
        return blocked
    if request.method == "GET":
        status, payload = _api("/me/preferences", token=token)
    else:
        status, payload = _api("/me/preferences", method="PATCH", token=token, data={
            "email_notifications": "email_notifications" in request.POST,
            "push_notifications": "push_notifications" in request.POST,
        })
    if status == 200 and (set(payload) != {"email_notifications", "push_notifications"}
                          or any(type(value) is not bool for value in payload.values())):
        status = 503
    if status == 200:
        response = render(request, "preferences.html", {"preferences": payload})
    else:
        response = render(request, "status.html", {"title": "Preferences unavailable"}, status=503)
    if rotated:
        _set_credentials(response, rotated)
    return response


def _valid_privacy_receipt(item):
    return (isinstance(item, dict)
            and set(item) == {"id", "kind", "status", "created_at"}
            and valid_id(item["id"])
            and item["kind"] in {"access", "deletion"}
            and item["status"] == "received"
            and isinstance(item["created_at"], str)
            and len(item["created_at"]) <= 64)


def privacy_requests(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    account_data, token, rotated, blocked = _account_access(request)
    if blocked is not None:
        return blocked
    if request.method == "POST":
        kind = request.POST.get("kind", "")
        if kind not in {"access", "deletion"}:
            response = render(request, "privacy_requests.html", {
                "error": "Select a valid request type", "items": [],
            }, status=400)
        else:
            status, payload = _api("/me/privacy-requests", method="POST", token=token, data={
                "kind": kind, "current_password": request.POST.get("current_password", ""),
            })
            if status in (200, 201) and _valid_privacy_receipt(payload):
                response = render(request, "privacy_requests.html", {
                    "receipt": payload, "items": [payload],
                })
            else:
                response = render(request, "privacy_requests.html", {
                    "error": payload.get("detail", "Privacy request unavailable"), "items": [],
                }, status=401 if status == 401 else 400 if status == 400 else 503)
    else:
        status, payload = _api("/me/privacy-requests", token=token)
        items = payload.get("items")
        if status == 200 and (not isinstance(items, list) or len(items) > 2
                              or any(not _valid_privacy_receipt(item) for item in items)):
            status = 503
        response = (render(request, "privacy_requests.html", {"items": items}) if status == 200
                    else render(request, "status.html", {"title": "Privacy requests unavailable"}, status=503))
    if rotated:
        _set_credentials(response, rotated)
    return response


@require_POST
def logout(request):
    refresh = request.COOKIES.get(REFRESH_COOKIE)
    confirmed = True
    if refresh:
        status, _ = _api("/auth/logout", method="POST", data={"refresh_token": refresh})
        confirmed = status == 204
    response = redirect("feed") if confirmed else render(request, "status.html", {
        "title": "Signed out on this browser. Server session revocation could not be confirmed.",
    }, status=503)
    _clear_credentials(response)
    return response


@require_GET
def gated_creator(request):
    return render(request, "status.html", {"title": "Creator publishing is awaiting provider and eligibility approval."}, status=503)


@require_GET
def points(request):
    cursor = request.GET.get("cursor")
    if (set(request.GET) - {"cursor"} or len(request.GET.getlist("cursor")) > 1
            or cursor is not None and not valid_id(cursor)):
        return render(request, "status.html", {"title": "Invalid points page."}, status=400)
    status, account, rotated = _own_account(request)
    if status != 200:
        response = redirect("login") if status == 401 else render(
            request, "status.html", {"title": "Account unavailable"}, status=503)
        if status == 401:
            _clear_credentials(response)
        elif rotated:
            _set_credentials(response, rotated)
        return response
    token = rotated["access_token"] if rotated else request.COOKIES.get(ACCESS_COOKIE)
    balance_status, balance = _api("/creators/me/points", token=token)
    query = "?" + urlencode({"cursor": cursor}) if cursor else ""
    page_status, page = _api("/creators/me/points/entries" + query, token=token)
    if balance_status == 200 and not valid_points_balance(balance):
        balance_status = 503
    if page_status == 200 and (balance_status != 200 or not valid_points_page(
            page, balance["creator_id"], cursor=cursor)):
        page_status = 503
    if balance_status == 200 and page_status == 200:
        response = render(request, "points.html", {
            "balance": balance, "items": page["items"],
            "next_cursor": page["next_cursor"], "account": account,
        })
    else:
        forbidden = 403 in (balance_status, page_status)
        response = render(request, "status.html", {
            "title": "Approved creator access is required." if forbidden else "Lone Stars unavailable."
        }, status=403 if forbidden else 503)
    if rotated:
        _set_credentials(response, rotated)
    return response
