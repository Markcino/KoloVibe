"""Bounded Cloudflare Stream client for the restricted pilot."""

from datetime import timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


UID = re.compile(r"[0-9a-f]{32}")
UPLOAD_URL = re.compile(r"https://upload\.videodelivery\.net/[0-9a-f]{32}")
MAX_WEBHOOK_BYTES = 16_384
UPLOAD_DURATION_SECONDS = 300
UPLOAD_LIFETIME = timedelta(minutes=10)
PLAYBACK_LIFETIME = timedelta(minutes=5)


class StreamUnavailable(Exception):
    pass


class InvalidStreamWebhook(Exception):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _private_value(name):
    try:
        path = Path(os.environ[name])
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError("Stream secret file must be private")
        value = path.read_text().strip()
        if len(value) < 24 or any(character.isspace() for character in value):
            raise ValueError("Invalid Stream secret")
        return value
    except (KeyError, OSError, ValueError):
        raise StreamUnavailable("Stream credentials unavailable") from None


def _call(method, resource, payload=None):
    account = os.environ.get("KOLOVIBE_STREAM_ACCOUNT_ID", "")
    if not UID.fullmatch(account):
        raise StreamUnavailable("Stream account unavailable")
    token = _private_value("KOLOVIBE_STREAM_API_TOKEN_FILE")
    request = Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/stream/{resource}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "Accept": "application/json"},
        method=method,
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=5) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Invalid Stream response length")
        data = json.loads(raw)
        if data["success"] is not True or not isinstance(data["result"], dict):
            raise ValueError("Invalid Stream response")
        return data["result"]
    except HTTPError as error:
        error.close()
        raise StreamUnavailable("Stream request failed") from None
    except (OSError, ValueError, KeyError, TypeError):
        raise StreamUnavailable("Stream request failed") from None


def create_upload(video_id, expires_at):
    result = _call("POST", "direct_upload", {
        "expiry": expires_at.isoformat(),
        "maxDurationSeconds": UPLOAD_DURATION_SECONDS,
        "requireSignedURLs": True,
        "meta": {"kolovibe_video_id": str(video_id)},
    })
    uid, url = result.get("uid"), result.get("uploadURL")
    if (not isinstance(uid, str) or not UID.fullmatch(uid)
            or not isinstance(url, str) or not UPLOAD_URL.fullmatch(url)
            or not url.endswith("/" + uid)):
        raise StreamUnavailable("Unexpected Stream upload link")
    return uid, url


def asset_is_ready(uid, video_id):
    if not UID.fullmatch(uid):
        raise StreamUnavailable("Invalid Stream asset")
    result = _call("GET", uid)
    meta, status = result.get("meta"), result.get("status")
    if (result.get("uid") != uid or result.get("requireSignedURLs") is not True
            or not isinstance(meta, dict) or meta.get("kolovibe_video_id") != str(video_id)
            or not isinstance(status, dict)):
        raise StreamUnavailable("Stream asset binding or privacy check failed")
    return result.get("readyToStream") is True and status.get("state") == "ready"


def webhook_asset(raw, header):
    if (not 0 < len(raw) <= MAX_WEBHOOK_BYTES or not isinstance(header, str)
            or len(header) > 160):
        raise InvalidStreamWebhook
    parts = header.split(",")
    if len(parts) != 2:
        raise InvalidStreamWebhook
    fields = dict(part.strip().split("=", 1) for part in parts if "=" in part)
    stamp, signature = fields.get("time", ""), fields.get("sig1", "")
    if (not re.fullmatch(r"[0-9]{10}", stamp) or not re.fullmatch(r"[0-9a-f]{64}", signature)
            or abs(time.time() - int(stamp)) > 300):
        raise InvalidStreamWebhook
    secret = _private_value("KOLOVIBE_STREAM_WEBHOOK_SECRET_FILE")
    expected = hmac.new(secret.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise InvalidStreamWebhook
    try:
        data = json.loads(raw)
        uid, status = data["uid"], data["status"]
        if not isinstance(uid, str) or not UID.fullmatch(uid) or not isinstance(status, dict):
            raise ValueError("Invalid webhook")
        return uid, data.get("readyToStream") is True and status.get("state") == "ready"
    except (ValueError, KeyError, TypeError):
        raise InvalidStreamWebhook from None



def signed_playback(uid, expires_at):
    host = os.environ.get("KOLOVIBE_STREAM_PLAYBACK_HOST", "")
    if not UID.fullmatch(uid) or not re.fullmatch(r"customer-[a-z0-9]+\.cloudflarestream\.com", host):
        raise StreamUnavailable("Stream playback configuration unavailable")
    token = _call("POST", f"{uid}/token", {"exp": int(expires_at.timestamp())}).get("token")
    if (not isinstance(token, str) or len(token) > 4096
            or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token)):
        raise StreamUnavailable("Unexpected Stream playback token")
    return f"https://{host}/{token}/manifest/video.m3u8"
