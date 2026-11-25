"""Bounded public account routes; identity owns credentials and sessions."""

import ipaddress
import json
import uuid
from urllib.error import HTTPError, URLError

from django.conf import settings

from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .internal_client import signed_internal_request

MAX_BODY = 4096
MAX_RESPONSE = 8192


def _json(data, status):
    if status == 204:
        return HttpResponse(status=204)
    return JsonResponse(data, status=status)


def _invoke(path, data, success_statuses, *, max_response=MAX_RESPONSE):
    try:
        body = json.dumps(data, separators=(",", ":")).encode()
        response = signed_internal_request("identity", path, method="POST", payload=body)
        with response:
            status = response.status
            raw = response.read(max_response + 1)
        if len(raw) > max_response or status not in success_statuses:
            raise ValueError("Unexpected identity response")
        if status == 204 and raw:
            raise ValueError("Unexpected identity response body")
        result = json.loads(raw) if raw else {}
        if not isinstance(result, dict):
            raise ValueError("Invalid identity response")
        if status == 202 and path == "/internal/auth/login" and (
            set(result) != {"mfa_required", "challenge_token", "expires_in"}
            or result["mfa_required"] is not True
            or not isinstance(result["challenge_token"], str)
            or not 32 <= len(result["challenge_token"]) <= 128
            or type(result["expires_in"]) is not int or result["expires_in"] != 300
        ):
            raise ValueError("Invalid MFA challenge response")
        return _json(result, status)
    except HTTPError as error:
        if error.code not in {400, 401, 403, 404, 409, 429, 503}:
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
        payload = {"detail": detail}
        if (error.code == 409 and path == "/internal/auth/privacy-requests"
                and result.get("code") == "request_open"):
            payload["code"] = "request_open"
        if (error.code == 409 and path in ("/internal/auth/register", "/internal/auth/legal")
                and result.get("code") == "legal_version_outdated"):
            payload["code"] = "legal_version_outdated"
        return _json(payload, error.code)
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


def _client_origin(request):
    """The caller's address, but only when the edge is configured to vouch for it.

    The gateway sits behind a proxy, so its own peer address is the proxy for every caller. A header
    is believed only when KOLOVIBE_TRUSTED_CLIENT_IP_HEADER names one the edge overwrites on every
    request; with no such header identity applies address-level limits alone.
    """
    header = getattr(settings, "KOLOVIBE_TRUSTED_CLIENT_IP_HEADER", "")
    if not header:
        return None
    value = request.META.get("HTTP_" + header.upper().replace("-", "_"), "")
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _with_origin(request, data):
    origin = _client_origin(request)
    return {**data, "origin": origin} if origin else data


@require_POST
def register(request):
    try:
        # Decision B: `accepted` names the versions of the terms and privacy notice the person saw; Identity checks them.
        data = _body(request, {"email", "password", "display_name", "accepted", "marketing_consent"})
        if not isinstance(data.get("accepted"), dict) or len(data["accepted"]) > 4:
            raise ValueError
        if "marketing_consent" in data and type(data["marketing_consent"]) is not bool:
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid registration"}, 400)
    return _invoke("/internal/auth/register", _with_origin(request, data), {201})


@require_POST
def resend_verification(request):
    try:
        data = _body(request, {"email"})
        if set(data) != {"email"}:
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid verification request"}, 400)
    return _invoke("/internal/auth/verification/resend", _with_origin(request, data), {204})


@require_POST
def verify_email(request):
    try:
        data = _body(request, {"email", "code"})
        # {"email", "code"} is the six-digit contract. A bare long "code" is the retired link,
        # accepted only while identity still honours pending ones (ADR-013 amendment A-1).
        if set(data) not in ({"email", "code"}, {"code"}):
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid verification"}, 400)
    return _invoke("/internal/auth/verify", _with_origin(request, data), {200})


@require_POST
def request_password_reset(request):
    try:
        data = _body(request, {"email"})
        if set(data) != {"email"}:
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid reset request"}, 400)
    return _invoke("/internal/auth/password/reset-request", _with_origin(request, data), {204})


@require_POST
def reset_password(request):
    try:
        data = _body(request, {"email", "code", "new_password"})
        if set(data) not in ({"email", "code", "new_password"}, {"code", "new_password"}):
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid reset request"}, 400)
    return _invoke("/internal/auth/password/reset", _with_origin(request, data), {204})


@never_cache
@require_POST
def reauthenticate(request):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    try:
        data = _body(request, {"current_password"})
        if (set(data) != {"current_password"} or not isinstance(data["current_password"], str)
                or not 1 <= len(data["current_password"]) <= 128):
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Reauthentication failed"}, 400)
    result = _invoke("/internal/auth/reauthenticate", {"access_token": token, **data}, {200})
    if result.status_code != 200:
        return result
    try:
        payload = json.loads(result.content)
        if (set(payload) != {"reauth_token", "expires_at"}
                or not isinstance(payload["reauth_token"], str)
                or not 32 <= len(payload["reauth_token"]) <= 128
                or not isinstance(payload["expires_at"], str)
                or len(payload["expires_at"]) > 64):
            raise ValueError
        expiry = parse_datetime(payload["expires_at"])
        if expiry is None or expiry.tzinfo is None:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        return _json({"detail": "Identity unavailable"}, 503)
    return result


@never_cache
@require_POST
def step_up(request):
    """Decision G: obtain a purpose-bound proof from Identity. Identity alone knows the purposes and their bindings."""
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    try:
        data = _body(request, {"current_password", "purpose", "resource_id"})
        if (not {"current_password", "purpose"} <= set(data)
                or not isinstance(data["current_password"], str) or not 1 <= len(data["current_password"]) <= 128
                or not isinstance(data["purpose"], str) or not 3 <= len(data["purpose"]) <= 64
                or ("resource_id" in data and not isinstance(data["resource_id"], str))):
            raise ValueError
        if "resource_id" in data:
            data["resource_id"] = str(uuid.UUID(data["resource_id"]))
    except (ValueError, UnicodeError, AttributeError):
        return _json({"detail": "Step-up failed"}, 400)
    result = _invoke("/internal/auth/step-up", {"access_token": token, **data}, {200})
    if result.status_code != 200:
        return result
    try:
        payload = json.loads(result.content)
        if (set(payload) != {"step_up_token", "purpose", "expires_at"} or payload["purpose"] != data["purpose"]
                or not isinstance(payload["step_up_token"], str) or not 32 <= len(payload["step_up_token"]) <= 128
                or not isinstance(payload["expires_at"], str) or len(payload["expires_at"]) > 64):
            raise ValueError
        expiry = parse_datetime(payload["expires_at"])
        if expiry is None or expiry.tzinfo is None:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        return _json({"detail": "Identity unavailable"}, 503)
    return result


@never_cache
@require_http_methods(["PATCH"])
def change_password(request):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    try:
        data = _body(request, {"current_password", "new_password"})
        if set(data) != {"current_password", "new_password"}:
            raise ValueError
    except (ValueError, UnicodeError):
        return _json({"detail": "Invalid password change"}, 400)
    return _invoke("/internal/auth/password/change", {"access_token": token, **data}, {204})


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


@never_cache
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


@never_cache
@require_GET
def sessions(request):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    return _invoke("/internal/auth/sessions", {"access_token": token}, {200})


@never_cache
@require_http_methods(["DELETE"])
def revoke_session(request, session_id):
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    return _invoke("/internal/auth/sessions",
                   {"access_token": token, "session_id": str(session_id)}, {204})


@never_cache
@require_http_methods(["GET", "PATCH"])
def me(request):
    if request.method == "PATCH":
        token = _bearer(request)
        if token is None:
            return _json({"detail": "Unauthorized"}, 401)
        try:
            data = _body(request, {"display_name"})
            if set(data) != {"display_name"}:
                raise ValueError
        except (ValueError, UnicodeError):
            return _json({"detail": "Invalid profile"}, 400)
        result = _invoke("/internal/auth/profile", {"access_token": token, **data}, {200})
        if result.status_code != 200:
            return result
        try:
            payload = json.loads(result.content)
            user = payload["user"]
            if not isinstance(user, dict) or not all(isinstance(user.get(k), str)
                                                    for k in ("id", "email", "display_name", "created_at")):
                raise ValueError
            if not isinstance(user.get("roles"), list) or not all(
                    isinstance(role, str) for role in user["roles"]):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return _json({"detail": "Identity unavailable"}, 503)
        return _json(user, 200)
    return current_account(request)


@never_cache
def current_account(request, *, require_verified_email=False):
    """Validate every protected request against identity's live session state.

    No positive-result cache: revocation applies to the next request even while
    the signed access credential remains inside its 300-second lifetime.
    """
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    data = {"access_token": token}
    if require_verified_email:
        data["include_email_verification"] = True
    result = _invoke("/internal/auth/validate", data, {200})
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
        if require_verified_email:
            if type(payload["email_verified"]) is not bool:
                raise ValueError("Invalid verification state")
            if not payload["email_verified"]:
                return _json({"detail": "Verified email required"}, 403)
    except (ValueError, KeyError, TypeError):
        return _json({"detail": "Identity unavailable"}, 503)
    return _json(user, 200)
