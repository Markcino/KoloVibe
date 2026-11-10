"""Gateway boundary for the private R2 VOD pipeline."""

from datetime import datetime
import json
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from uuid import UUID

from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .accounts import current_account
from .creator_onboarding import creator_eligibility
from .internal_client import signed_internal_request
from .videos import list_videos


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _safe_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        return False
    url = urlsplit(value)
    return (url.scheme == "https" and bool(re.fullmatch(r"[0-9a-f]{32}\.r2\.cloudflarestorage\.com", url.netloc))
            and url.path.endswith(".mp4") and bool(url.query) and not url.fragment)


def _valid_result(operation, data, payload):
    if not isinstance(data, dict):
        return False
    if operation in ("watch", "watch-check"):
        metadata = {"creator_id", "duration_ms", "revision"}
        expected = metadata | ({"playback_url", "expires_at"} if operation == "watch" else set())
        if (set(data) != expected or str(UUID(data["creator_id"])) != data["creator_id"]
                or type(data["duration_ms"]) is not int or not 1 <= data["duration_ms"] <= 300_000
                or type(data["revision"]) is not int or not 0 <= data["revision"] <= 2_147_483_647):
            return False
        if operation == "watch-check":
            return True
        data = {key: value for key, value in data.items() if key not in metadata}
        operation = "playback"
    if operation == "playback":
        return (set(data) == {"playback_url", "expires_at"} and _safe_url(data["playback_url"])
                and datetime.fromisoformat(data["expires_at"]).tzinfo is not None)
    if operation == "draft":
        return (set(data) == {"id", "creator_id", "title", "description", "state", "created_at"}
                and str(UUID(data["id"])) == data["id"] and data["creator_id"] == payload["creator_id"]
                and data["title"] == payload["title"].strip() and data["description"] == payload["description"]
                and data["state"] == "draft" and datetime.fromisoformat(data["created_at"]).tzinfo is not None)
    if operation in ("complete", "status"):
        return (set(data) == {"video_id", "state"} and data["video_id"] == payload["video_id"]
                and data["state"] in ("draft", "uploading", "processing", "failed", "review", "published", "rejected", "removed"))
    return (set(data) == {"video_id", "upload_id", "upload_url", "upload_headers", "expires_at", "max_bytes"}
            and data["video_id"] == payload["video_id"] and str(UUID(data["upload_id"])) == data["upload_id"]
            and _safe_url(data["upload_url"])
            and data["upload_headers"] == {"Content-Type": "video/mp4", "Content-Length": str(payload["size_bytes"]),
                                           "If-None-Match": "*"}
            and datetime.fromisoformat(data["expires_at"]).tzinfo is not None
            and type(data["max_bytes"]) is int and data["max_bytes"] == 50 * 1024 * 1024)


def forward_media(operation, data, success):
    try:
        with signed_internal_request(
            "content", f"/internal/videos/media/{operation}", method="POST",
            payload=json.dumps(data, separators=(",", ":")).encode(), timeout=8,
        ) as response:
            if response.status in success:
                raw = response.read(32769)
                if len(raw) <= 32768:
                    result = json.loads(raw)
                    if _valid_result(operation, result, data):
                        return JsonResponse(result, status=response.status)
    except HTTPError as error:
        with error:
            if error.code in (400, 403, 404, 409):
                try:
                    raw = error.read(513)
                    result = json.loads(raw) if len(raw) <= 512 else None
                    if isinstance(result, dict) and set(result) == {"detail"} and isinstance(result["detail"], str):
                        return _error(result["detail"], error.code)
                except (OSError, ValueError, TypeError, AttributeError):
                    pass
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    return _error("Video service unavailable", 503)


def _eligible_creator(request):
    eligibility = creator_eligibility(request)
    if eligibility.status_code != 200:
        return None, eligibility
    data = json.loads(eligibility.content)
    if not data["upload_eligible"]:
        return None, _error("Approved creator eligibility required", 403)
    return data["creator_id"], None


def video_collection(request):
    if request.method != "POST":
        return list_videos(request)
    return create_video_draft(request)


@never_cache
def create_video_draft(request):
    creator_id, error = _eligible_creator(request)
    if error is not None:
        return error
    try:
        if request.GET or len(request.body) > 32768:
            raise ValueError("Invalid draft")
        data = json.loads(request.body)
        if not isinstance(data, dict) or "title" not in data or set(data) - {"title", "description"}:
            raise ValueError("Invalid draft")
    except (ValueError, UnicodeError):
        return _error("Invalid video draft", 400)
    return forward_media("draft", {"creator_id": creator_id, "title": data["title"],
                              "description": data.get("description", "")}, (201,))


@never_cache
@require_POST
def issue_video_upload(request, video_id):
    creator_id, error = _eligible_creator(request)
    if error is not None:
        return error
    key = request.headers.get("Idempotency-Key", "")
    try:
        if request.GET or len(request.body) > 128 or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
            raise ValueError("Invalid upload intent")
        data = json.loads(request.body)
        if (not isinstance(data, dict) or set(data) != {"size_bytes"}
                or type(data["size_bytes"]) is not int or not 0 < data["size_bytes"] <= 50 * 1024 * 1024):
            raise ValueError("Invalid upload size")
    except (ValueError, TypeError):
        return _error("Valid upload size and Idempotency-Key required", 400)
    return forward_media("intent", {"creator_id": creator_id, "video_id": str(video_id),
                               "idempotency_key": key, "size_bytes": data["size_bytes"]}, (200,))


@never_cache
def video_upload_status(request, video_id):
    if request.method not in ("POST", "GET"):
        return HttpResponseNotAllowed(["POST", "GET"])
    creator_id, error = _eligible_creator(request)
    if error is not None:
        return error
    if request.GET or request.body:
        return _error("Invalid upload request", 400)
    operation = "complete" if request.method == "POST" else "status"
    return forward_media(operation, {"creator_id": creator_id, "video_id": str(video_id)}, (200, 202))


@never_cache
@require_GET
def video_playback(request, video_id):
    account = current_account(request)
    if account.status_code != 200:
        return account
    if request.GET or request.body:
        return _error("Invalid playback request", 400)
    return forward_media("playback", {"video_id": str(video_id)}, (200,))
