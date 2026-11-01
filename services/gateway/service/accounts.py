"""Bounded public account routes; identity owns credentials and sessions."""

import json
from urllib.error import HTTPError, URLError

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .internal_client import signed_internal_request

MAX_BODY = 4096
MAX_RESPONSE = 8192


def _json(data, status):
    if status == 204:
        return HttpResponse(status=204)
    return JsonResponse(data, status=status)


def _invoke(path, data, success_statuses):
    try:
        body = json.dumps(data, separators=(",", ":")).encode()
        response = signed_internal_request("identity", path, method="POST", payload=body)
        with response:
            status = response.status
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE or status not in success_statuses:
            raise ValueError("Unexpected identity response")
        result = json.loads(raw) if raw else {}
        if not isinstance(result, dict):
            raise ValueError("Invalid identity response")
        if status == 202 and (
            set(result) != {"mfa_required", "challenge_token", "expires_in"}
            or result["mfa_required"] is not True
            or not isinstance(result["challenge_token"], str)
            or not 32 <= len(result["challenge_token"]) <= 128
            or type(result["expires_in"]) is not int or result["expires_in"] != 300
        ):
            raise ValueError("Invalid MFA challenge response")
        return _json(result, status)
    except HTTPError as error:
        if error.code not in {400, 401, 403, 409, 429, 503}:
            return _json({"detail": "Identity unavailable"}, 503)
        try:
            raw = error.read(MAX_RESPONSE + 1)
            result = json.loads(raw)
            if len(raw) > MAX_RESPONSE or not isinstance(result, dict):
                raise ValueError("Invalid identity error")
            detail = result.get("detail")
            if not isinstance(detail, str) or len(detail) > 160:
                raise ValueError("Invalid identity error")
        except (ValueError, TypeError, UnicodeError):
            return _json({"detail": "Identity unavailable"}, 503)
        return _json({"detail": detail}, error.code)
    except (URLError, TimeoutError, OSError, KeyError, ValueError, TypeError, UnicodeError):
        return _json({"detail": "Identity unavailable"}, 503)


def _body(request, allowed):
    if len(request.body) > MAX_BODY:
        raise ValueError("Request too large")
    data = json.loads(request.body)
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("Invalid request")
    return data


def _bearer(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or len(header) > 2048:
        return None
    token = header[7:]
    return token if token and " " not in token else None


@require_POST
def register(request):
    try:
        data = _body(request, {"email", "password", "display_name"})
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid registration"}, 400)
    return _invoke("/internal/auth/register", data, {201})


@require_POST
def verify_email(request):
    try:
        data = _body(request, {"code"})
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid verification"}, 400)
    return _invoke("/internal/auth/verify", data, {200})


@require_POST
def login(request):
    try:
        data = _body(request, {"email", "password"})
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid credentials"}, 400)
    return _invoke("/internal/auth/login", data, {200, 202})


@require_POST
def verify_mfa(request):
    try:
        data = _body(request, {"challenge_token", "code"})
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid MFA challenge"}, 400)
    return _invoke("/internal/auth/mfa/verify", data, {200})


@require_POST
def refresh(request):
    try:
        data = _body(request, {"refresh_token"})
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid session"}, 400)
    return _invoke("/internal/auth/refresh", data, {200})


@require_POST
def logout(request):
    token = _bearer(request)
    if token is not None:
        return _invoke("/internal/auth/revoke", {"access_token": token}, {204})
    try:
        data = _body(request, {"refresh_token"})
        if not isinstance(data.get("refresh_token"), str):
            raise ValueError("Invalid token")
    except (ValueError, UnicodeError):
        return _json({"detail": "Unauthorized"}, 401)
    return _invoke("/internal/auth/revoke", data, {204})


@require_GET
def me(request):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    result = _invoke("/internal/auth/validate", {"access_token": token}, {200})
    if result.status_code != 200:
        return result
    try:
        payload = json.loads(result.content)
        user = payload["user"]
        if not isinstance(user, dict) or not all(isinstance(user.get(k), str)
                                                 for k in ("id", "email", "display_name", "created_at")):
            raise ValueError("Invalid user")
        if not isinstance(user.get("roles"), list) or not all(
                isinstance(role, str) for role in user["roles"]):
            raise ValueError("Invalid user")
    except (ValueError, KeyError, TypeError):
        return _json({"detail": "Identity unavailable"}, 503)
    return _json(user, 200)
