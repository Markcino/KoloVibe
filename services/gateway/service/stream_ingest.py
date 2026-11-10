"""Gateway boundary for eligible creator uploads and Stream callbacks."""

from base64 import b64encode
from datetime import datetime
import json
import re
from urllib.error import HTTPError
from uuid import UUID

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .accounts import current_account
from .creator_onboarding import creator_eligibility
from .internal_client import signed_internal_request
from .videos import list_videos


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _valid_result(operation, data, payload):
    if not isinstance(data, dict):
        return False
    if operation == "playback":
        return (set(data) == {"playback_url", "expires_at"}
                and bool(re.fullmatch(
                    r"https://customer-[a-z0-9]+\.cloudflarestream\.com/[A-Za-z0-9_.-]{1,4096}/manifest/video\.m3u8",
                    data["playback_url"],
                ))
                and datetime.fromisoformat(data["expires_at"]).tzinfo is not None)
    if operation == "draft":
        return (set(data) == {"id", "creator_id", "title", "description", "state", "created_at"}
                and str(UUID(data["id"])) == data["id"] and data["creator_id"] == payload["creator_id"]
                and data["title"] == payload["title"].strip() and data["description"] == payload["description"]
                and data["state"] == "draft"
                and datetime.fromisoformat(data["created_at"]).tzinfo is not None)
    return (set(data) == {"video_id", "upload_id", "upload_url", "expires_at", "max_bytes"}
            and data["video_id"] == payload["video_id"] and str(UUID(data["upload_id"])) == data["upload_id"]
            and bool(re.fullmatch(r"https://upload\.videodelivery\.net/[0-9a-f]{32}", data["upload_url"]))
            and datetime.fromisoformat(data["expires_at"]).tzinfo is not None
            and type(data["max_bytes"]) is int and 0 < data["max_bytes"] <= 200_000_000)


def _forward(operation, data, success):
    try:
        with signed_internal_request(
            "content", f"/internal/videos/stream/{operation}", method="POST",
            payload=json.dumps(data, separators=(",", ":")).encode(), timeout=8,
        ) as response:
            if response.status == success:
                if success == 204:
                    return HttpResponse(status=204)
                raw = response.read(8193)
                if len(raw) <= 8192:
                    result = json.loads(raw)
                    if _valid_result(operation, result, data):
                        return JsonResponse(result, status=success)
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
        if request.GET or len(request.body) > 8192:
            raise ValueError("Invalid draft")
        data = json.loads(request.body)
        if not isinstance(data, dict) or "title" not in data or set(data) - {"title", "description"}:
            raise ValueError("Invalid draft")
    except (ValueError, UnicodeError):
        return _error("Invalid video draft", 400)
    return _forward("draft", {"creator_id": creator_id, "title": data["title"],
                              "description": data.get("description", "")}, 201)


@never_cache
@require_POST
def issue_video_upload(request, video_id):
    creator_id, error = _eligible_creator(request)
    if error is not None:
        return error
    key = request.headers.get("Idempotency-Key", "")
    if request.GET or request.body or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
        return _error("Valid Idempotency-Key and empty request body required", 400)
    return _forward("intent", {"creator_id": creator_id, "video_id": str(video_id),
                               "idempotency_key": key}, 200)


@require_POST
def cloudflare_stream_webhook(request):
    signature = request.headers.get("Webhook-Signature", "")
    if not signature or len(signature) > 160:
        return _error("Invalid Stream webhook", 403)
    if request.GET or not 0 < len(request.body) <= 16_384:
        return _error("Invalid Stream webhook body", 400)
    return _forward("webhook", {"body": b64encode(request.body).decode("ascii"), "signature": signature}, 204)



@never_cache
@require_GET
def video_playback(request, video_id):
    account = current_account(request)
    if account.status_code != 200:
        return account
    if request.GET or request.body:
        return _error("Invalid playback request", 400)
    return _forward("playback", {"video_id": str(video_id)}, 200)
