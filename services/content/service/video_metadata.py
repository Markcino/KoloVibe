"""Bounded video metadata validation and private poster URL serialization."""

import re

from . import media_storage as storage
from .models import Video

FIELDS = {"title", "description", "category", "tags", "cover_time_ms"}
FAILURES = {"invalid_media", "cover_out_of_range", "processing_unavailable", "poster_failed",
            "upload_missing", "upload_changed"}


def metadata(data, *, creating=False, duration_ms=None):
    if (not isinstance(data, dict) or not data or set(data) - FIELDS
            or creating and not {"title", "category"} <= set(data)):
        raise ValueError("Invalid metadata")
    result = dict(data)
    if "title" in result:
        value = result["title"]
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 160:
            raise ValueError("Invalid title")
        result["title"] = value.strip()
    if "description" in result and (not isinstance(result["description"], str)
                                      or len(result["description"]) > 2000):
        raise ValueError("Invalid description")
    if "category" in result and result["category"] not in Video.Category.values:
        raise ValueError("Invalid category")
    if "tags" in result:
        values = result["tags"]
        if not isinstance(values, list) or len(values) > 5:
            raise ValueError("Invalid tags")
        normalized = []
        for tag in values:
            if not isinstance(tag, str) or len(tag) > 64:
                raise ValueError("Invalid tag")
            tag = tag.strip().removeprefix("#").lower()
            if not re.fullmatch(r"[a-z0-9_]{1,30}", tag):
                raise ValueError("Invalid tag")
            if tag not in normalized:
                normalized.append(tag)
        result["tags"] = normalized
    if "cover_time_ms" in result and result["cover_time_ms"] is not None:
        cover = result["cover_time_ms"]
        if (type(cover) is not int or not 0 <= cover <= 300_000
                or duration_ms is not None and cover > duration_ms):
            raise ValueError("Invalid cover time")
    return result


def poster_url(video):
    if not video.poster_asset_id:
        return None
    try:
        return storage.sign_playback(video.poster_asset_id, 300)
    except storage.StorageUnavailable:
        return None


def item(video):
    result = {"id": str(video.id), "creator_id": str(video.creator_id),
              "title": video.title, "description": video.description, "state": video.state,
              "created_at": video.created_at.isoformat(), "visibility": video.visibility,
              "published_at": video.published_at.isoformat() if video.published_at else None,
              "category": video.category, "tags": video.tags, "cover_time_ms": video.cover_time_ms,
              "poster_url": poster_url(video)}
    if video.duration_seconds is not None:
        result["duration_seconds"] = video.duration_seconds
    if video.duration_ms is not None:
        result["duration_ms"] = video.duration_ms
    return result
