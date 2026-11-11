"""Bounded, signed Content reads for creator totals and ordered public lookups."""

import json
from urllib.error import HTTPError
from uuid import UUID

from .internal_client import signed_internal_request
from .video_validation import valid_video


def _post(path, payload):
    try:
        with signed_internal_request("content", path, method="POST",
                                     payload=json.dumps(payload, separators=(",", ":")).encode()) as response:
            raw = response.read(2000001)
            if response.status != 200 or len(raw) > 2000000:
                return None
        return json.loads(raw)
    except HTTPError as error:
        error.close()
        return None
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return None


def lookup_public_videos(ids):
    try:
        if (not isinstance(ids, list) or len(ids) > 50 or len(set(ids)) != len(ids)
                or any(not isinstance(value, str) or str(UUID(value)) != value for value in ids)):
            return None
        data = _post("/internal/videos/lookup", {"ids": ids})
        if (not isinstance(data, dict) or set(data) != {"items"} or not isinstance(data["items"], list)
                or len(data["items"]) > len(ids)
                or not all(valid_video(item, public=True) for item in data["items"])):
            return None
        found = [item["id"] for item in data["items"]]
        if len(set(found)) != len(found) or found != [value for value in ids if value in set(found)]:
            return None
        return data["items"]
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def published_video_count(creator_id):
    data = _post("/internal/videos/published-count", {"creator_id": creator_id})
    if (not isinstance(data, dict) or set(data) != {"creator_id", "published_video_count"}
            or data["creator_id"] != creator_id or type(data["published_video_count"]) is not int
            or data["published_video_count"] < 0):
        return None
    return data["published_video_count"]
