"""Decision B at the edge: the current legal texts (public), and the signed-in acceptance and marketing-consent state.

Identity owns the documents, their versions and the records. The Gateway checks the shape of every answer so a fault in
Identity cannot hand the app an unexpected field, and passes only `legal_version_outdated` through as a code.
"""
import json
import re

from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .accounts import _bearer, _body, _invoke, _json

KINDS = ("terms", "privacy", "marketing")
REQUIRED = ("terms", "privacy")
STATUSES = ("pending_legal_review", "approved")
TEXT_LIMIT = 32_768
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SHA = re.compile(r"[0-9a-f]{64}")
_SUMMARY = {"kind", "title", "version", "effective_at", "status", "sha256"}


def _version(value):
    return isinstance(value, str) and 1 <= len(value) <= 32


def _summary(item, kind=None):
    if (not isinstance(item, dict) or item.get("kind") not in KINDS or (kind and item["kind"] != kind)
            or not isinstance(item.get("title"), str) or not 1 <= len(item["title"]) <= 80
            or not _version(item.get("version")) or not isinstance(item.get("effective_at"), str)
            or not _DATE.fullmatch(item["effective_at"]) or item.get("status") not in STATUSES
            or not isinstance(item.get("sha256"), str) or not _SHA.fullmatch(item["sha256"])):
        raise ValueError


def _stamp(value):
    if value is not None and (not isinstance(value, str) or len(value) > 64):
        raise ValueError


def _state(data):
    if set(data) != {"documents", "acceptance_required", "marketing"} or type(data["acceptance_required"]) is not bool:
        raise ValueError
    documents = data["documents"]
    if not isinstance(documents, list) or [d.get("kind") if isinstance(d, dict) else None for d in documents] != list(REQUIRED):
        raise ValueError
    for item in documents:
        if set(item) != _SUMMARY | {"accepted_version", "accepted_at"}:
            raise ValueError
        _summary(item)
        if item["accepted_version"] is not None and not _version(item["accepted_version"]):
            raise ValueError
        _stamp(item["accepted_at"])
    marketing = data["marketing"]
    if (not isinstance(marketing, dict) or set(marketing) != {"granted", "version", "updated_at"}
            or type(marketing["granted"]) is not bool or not _version(marketing["version"])):
        raise ValueError
    _stamp(marketing["updated_at"])


def _checked(result, check):
    if result.status_code != 200:
        return result
    try:
        data = json.loads(result.content)
        check(data)
    except (ValueError, TypeError, KeyError, AttributeError):
        return _json({"detail": "Identity unavailable"}, 503)
    return _json(data, 200)


@require_http_methods(["GET"])
def document(request, kind):
    """Public: the current text of one document, readable before registration."""
    if kind not in KINDS:
        return _json({"detail": "Not found"}, 404)

    def check(data):
        if set(data) != _SUMMARY | {"text"} or not isinstance(data["text"], str) or not 1 <= len(data["text"]) <= TEXT_LIMIT:
            raise ValueError
        _summary(data, kind)

    response = _checked(_invoke("/internal/auth/legal/document", {"kind": kind}, {200}, max_response=TEXT_LIMIT * 2),
                        check)
    if response.status_code == 200:
        response["Cache-Control"] = "public, max-age=300"
    return response


@never_cache
@require_http_methods(["GET", "POST"])
def acceptance(request):
    """GET the acceptance state; POST `{accepted: {kind: version}}` to accept the current required versions."""
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    data = {"access_token": token, "operation": "get"}
    if request.method == "POST":
        try:
            fields = _body(request, {"accepted"})
            accepted = fields["accepted"]
            if (set(fields) != {"accepted"} or not isinstance(accepted, dict) or not accepted
                    or not set(accepted) <= set(REQUIRED) or not all(_version(v) for v in accepted.values())):
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeError):
            return _json({"detail": "Invalid acceptance"}, 400)
        data = {"access_token": token, "operation": "accept", "accepted": accepted}
    return _checked(_invoke("/internal/auth/legal", data, {200}), _state)


@never_cache
@require_http_methods(["PUT"])
def marketing_consent(request):
    """PUT `{granted, version}`: grant or withdraw the optional marketing consent for the version shown."""
    token = _bearer(request)
    if token is None:
        return _json({"detail": "Unauthorized"}, 401)
    try:
        fields = _body(request, {"granted", "version"})
        if set(fields) != {"granted", "version"} or type(fields["granted"]) is not bool or not _version(fields["version"]):
            raise ValueError
    except (ValueError, KeyError, TypeError, UnicodeError):
        return _json({"detail": "Invalid consent"}, 400)
    return _checked(_invoke("/internal/auth/legal", {"access_token": token, "operation": "marketing", **fields}, {200}),
                    _state)
