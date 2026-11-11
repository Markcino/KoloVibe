"""Public app-version policy; no client-supplied store destinations or I/O."""

import re
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

_NUMBER = r"(?:0|[1-9][0-9]*)"
_PRE = rf"(?:{_NUMBER}|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
_SEMVER = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-({_PRE}(?:\.{_PRE})*))?(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?",
    re.ASCII,
)


def version_key(value):
    """Strict SemVer 2.0 precedence, including prereleases; ignore build metadata."""
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("Invalid semantic version")
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise ValueError("Invalid semantic version")
    major, minor, patch, prerelease = match.groups()
    identifiers = tuple((0, int(part)) if part.isascii() and part.isdigit() else (1, part)
                        for part in prerelease.split(".")) if prerelease else ()
    return (int(major), int(minor), int(patch)), prerelease is None, identifiers


def validate_configuration(minimum, latest, store_url):
    """Called during settings load; reject unsafe or inconsistent operator input."""
    minimum, latest, store_url = minimum or None, latest or None, store_url or None
    try:
        for version in (minimum, latest):
            if version is not None:
                version_key(version)
        if minimum and latest and version_key(minimum) > version_key(latest):
            raise ValueError
        if store_url is not None:
            URLValidator(schemes=["https"])(store_url)
            parsed = urlsplit(store_url)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                    or parsed.password is not None or "\\" in store_url
                    or any(char.isspace() or ord(char) < 32 for char in store_url)):
                raise ValueError
    except (ValueError, TypeError, ValidationError):
        raise RuntimeError("Invalid app compatibility configuration") from None
    return {"minimum_version": minimum, "latest_version": latest, "store_url": store_url}


@never_cache
@require_GET
def compatibility(request):
    try:
        if (set(request.GET) != {"platform", "version"}
                or any(len(request.GET.getlist(key)) != 1 for key in request.GET)
                or request.GET["platform"] not in {"ios", "android"}):
            raise ValueError
        client = version_key(request.GET["version"])
    except ValueError:
        return JsonResponse({"detail": "Invalid compatibility parameters"}, status=400)
    config = settings.APP_COMPATIBILITY[request.GET["platform"]]
    minimum, latest = config["minimum_version"], config["latest_version"]
    if minimum is not None and client < version_key(minimum):
        status = "update_required"
    elif latest is not None and client < version_key(latest):
        status = "update_available"
    elif minimum is not None or latest is not None:
        status = "supported"
    else:
        status = "unknown"
    return JsonResponse({"status": status, **config})
