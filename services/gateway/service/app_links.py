"""App-only share links (owner decision SIM-02): shared videos open the KoloVibe app, never a website.

A share link is `<KOLOVIBE_APP_LINK_ORIGIN>/open/videos/<video_id>`. On a phone with the app installed the
operating system opens the app directly (iOS Universal Links, Android App Links), because this origin publishes the
two association files below. Without the app, the phone's browser reaches `open_video`, which only redirects to the
configured store listing. The redirect never reads the video, so it reveals nothing about whether a video exists or
is public; the app reads the video through the normal authorized API once it opens.

Nothing here serves HTML or any page content: the directive allows no public website.
"""

import os
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

SHARE_PATH = "/open/videos/"
_IOS_APP_ID = re.compile(r"[A-Z0-9]{10}\.[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", re.ASCII)
_ANDROID_PACKAGE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+", re.ASCII)
_FINGERPRINT = re.compile(r"[0-9A-F]{2}(?::[0-9A-F]{2}){31}", re.ASCII)
_IOS_AGENT = re.compile(r"\b(?:iPhone|iPad|iPod)\b")
_ANDROID_AGENT = re.compile(r"\bAndroid\b")
_NO_APP_TEXT = "Open this link on a phone with the KoloVibe app installed.\n"


def validate_origin(value, name):
    """An HTTPS origin with no credentials, path, query or fragment; empty means unconfigured."""
    if value is None or value == "":
        return None
    try:
        URLValidator(schemes=["https"])(value)
        parsed = urlsplit(value)
        _ = parsed.port  # URL splitting validates malformed/out-of-range ports lazily.
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or "\\" in value or any(ord(c) < 33 for c in value)):
            raise ValueError
        return parsed.geturl().rstrip("/")
    except (ValueError, TypeError, ValidationError):
        raise RuntimeError(f"Invalid {name}") from None


def load_configuration(environ=os.environ):
    """Called during settings load; reject unsafe or inconsistent operator input."""
    origin = validate_origin(environ.get("KOLOVIBE_APP_LINK_ORIGIN"), "KOLOVIBE_APP_LINK_ORIGIN")
    ios = environ.get("KOLOVIBE_APP_LINK_IOS_APP_ID") or None
    package = environ.get("KOLOVIBE_APP_LINK_ANDROID_PACKAGE") or None
    raw = environ.get("KOLOVIBE_APP_LINK_ANDROID_SHA256") or ""
    fingerprints = [value.strip() for value in raw.split(",")] if raw else []
    if ios is not None and (len(ios) > 166 or not _IOS_APP_ID.fullmatch(ios)):
        raise RuntimeError("Invalid KOLOVIBE_APP_LINK_IOS_APP_ID")
    if package is not None and (len(package) > 150 or not _ANDROID_PACKAGE.fullmatch(package)):
        raise RuntimeError("Invalid KOLOVIBE_APP_LINK_ANDROID_PACKAGE")
    if (len(fingerprints) > 4 or len(set(fingerprints)) != len(fingerprints)
            or any(not _FINGERPRINT.fullmatch(value) for value in fingerprints)
            or bool(package) != bool(fingerprints)):
        raise RuntimeError("Invalid KOLOVIBE_APP_LINK_ANDROID_SHA256")
    if (ios or package) and origin is None:
        raise RuntimeError("App link associations need KOLOVIBE_APP_LINK_ORIGIN")
    return {"origin": origin, "ios_app_id": ios, "android_package": package,
            "android_fingerprints": fingerprints}


def _ready():
    config = settings.APP_LINKS
    return config["origin"] is not None and bool(config["ios_app_id"] or config["android_package"])


def share_url(video_id):
    """The app link for a video, or None while no app can claim the link (sharing then stays unavailable)."""
    return settings.APP_LINKS["origin"] + SHARE_PATH + str(video_id) if _ready() else None


def _cacheable(response):
    response["Cache-Control"] = "public, max-age=3600"
    return response


def _not_found():
    return JsonResponse({"detail": "Not found"}, status=404)


@require_GET
def apple_app_site_association(request):
    app_id = settings.APP_LINKS["ios_app_id"]
    if not _ready() or app_id is None:
        return _not_found()
    return _cacheable(JsonResponse({"applinks": {"details": [{
        "appIDs": [app_id],
        "components": [{"/": SHARE_PATH + "*", "comment": "Shared KoloVibe videos"}],
    }]}}))


@require_GET
def android_asset_links(request):
    config = settings.APP_LINKS
    if not _ready() or config["android_package"] is None:
        return _not_found()
    return _cacheable(JsonResponse([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": config["android_package"],
                   "sha256_cert_fingerprints": config["android_fingerprints"]},
    }], safe=False))


@never_cache
@require_GET
def open_video(request, video_id):
    """Reached only when the app did not claim the link: send a phone to its store, anything else gets one line.

    The video is deliberately not looked up, and the response is the same for every id.
    """
    agent = request.headers.get("User-Agent", "")[:512]
    platform = "ios" if _IOS_AGENT.search(agent) else "android" if _ANDROID_AGENT.search(agent) else None
    store = settings.APP_COMPATIBILITY[platform]["store_url"] if platform else None
    if store:
        response = HttpResponseRedirect(store)
    else:
        response = HttpResponse(_NO_APP_TEXT, content_type="text/plain; charset=utf-8")
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Content-Type-Options"] = "nosniff"
    return response
