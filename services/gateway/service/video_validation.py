"""Strict metadata/URL validation at the Content trust boundary."""

from datetime import datetime
import re
from urllib.parse import urlsplit
from uuid import UUID

CATEGORIES = {"hipco", "afrobeats", "comedy", "skits", "short_films", "culture", "documentaries"}
STATES = {"draft", "uploading", "processing", "failed", "review", "published", "rejected", "removed"}
LIBRARY_STATES = {"all", "draft", "in_progress", "review", "published", "rejected", "removed", "failed"}
METADATA_FIELDS = {"title", "description", "category", "tags", "cover_time_ms"}
FAILURES = {"invalid_media", "cover_out_of_range", "processing_unavailable", "poster_failed",
            "upload_missing", "upload_changed"}


def safe_url(value, suffix=".mp4"):
    if (not isinstance(value, str) or len(value) > 4096
            or any(ord(char) < 33 for char in value) or "\\" in value):
        return False
    url = urlsplit(value)
    return (url.scheme == "https" and bool(re.fullmatch(r"[0-9a-f]{32}\.r2\.cloudflarestorage\.com", url.netloc))
            and url.path.endswith(suffix) and bool(url.query) and not url.fragment)


def timestamp(value, nullable=False):
    if value is None:
        return nullable
    return isinstance(value, str) and len(value) <= 64 and datetime.fromisoformat(value).tzinfo is not None


def valid_video(item, *, creator_id=None, public=False, revision=False):
    required = {"id", "creator_id", "title", "description", "state", "created_at", "visibility",
                "published_at", "category", "tags", "cover_time_ms", "poster_url"}
    if revision:
        required.add("revision")
    if creator_id is not None and not public:
        required.add("edit_review")  # Decision A: only the owner's view carries the state of their edit review
    if (not isinstance(item, dict) or not required <= item.keys()
            or item.keys() - required - {"duration_seconds", "duration_ms"}
            or item["state"] not in STATES
            or public and (item["state"] != "published" or item["visibility"] != "public")
            or creator_id is not None and item["creator_id"] != creator_id
            or item["visibility"] not in {"private", "public", "unlisted"}
            or not isinstance(item["title"], str) or not 1 <= len(item["title"]) <= 160
            or not isinstance(item["description"], str) or len(item["description"]) > 2000
            or item["category"] is not None and item["category"] not in CATEGORIES):
        return False
    if not all(isinstance(item[name], str) and str(UUID(item[name])) == item[name] for name in ("id", "creator_id")):
        return False
    if not timestamp(item["created_at"]) or not timestamp(item["published_at"], nullable=True):
        return False
    tags = item["tags"]
    if (not isinstance(tags, list) or len(tags) > 5
            or not all(isinstance(tag, str) and re.fullmatch(r"[a-z0-9_]{1,30}", tag) for tag in tags)
            or len(set(tags)) != len(tags)):
        return False
    for name, minimum, maximum in (("duration_seconds", 0, 300), ("duration_ms", 1, 300_000)):
        if name in item and (type(item[name]) is not int or not minimum <= item[name] <= maximum):
            return False
    cover = item["cover_time_ms"]
    duration = item.get("duration_ms", item.get("duration_seconds", 300) * 1000)
    if cover is not None and (type(cover) is not int or not 0 <= cover <= duration):
        return False
    if item["poster_url"] is not None and not safe_url(item["poster_url"], ".jpg"):
        return False
    if revision and (type(item["revision"]) is not int or not 0 <= item["revision"] <= 2_147_483_647):
        return False
    if "edit_review" in required and not valid_edit_review(item["edit_review"]):
        return False
    return True


def valid_edit_review(review):
    """Null, or the newest pending or decided edit; the proposal is shown only while it is pending."""
    if review is None:
        return True
    from .reviewer_contracts import valid_edit_values
    if (not isinstance(review, dict)
            or set(review) != {"id", "status", "submitted_at", "decided_at", "reason_code", "proposed"}
            or not isinstance(review["id"], str) or str(UUID(review["id"])) != review["id"]
            or review["status"] not in {"pending", "approved", "rejected"}
            or not timestamp(review["submitted_at"])
            or not timestamp(review["decided_at"], nullable=review["status"] == "pending")
            or (review["status"] == "pending") != (review["decided_at"] is None)
            or review["reason_code"] is not None and (not isinstance(review["reason_code"], str)
                                                      or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", review["reason_code"]))
            or (review["status"] == "pending") != (review["proposed"] is not None)):
        return False
    return review["proposed"] is None or valid_edit_values(review["proposed"])


def checked_metadata(fields, *, creating=False):
    if (not isinstance(fields, dict) or not fields or set(fields) - METADATA_FIELDS
            or creating and not {"title", "category"} <= fields.keys()):
        raise ValueError
    fields = dict(fields)
    if "title" in fields:
        if not isinstance(fields["title"], str) or not 1 <= len(fields["title"].strip()) <= 160:
            raise ValueError
        fields["title"] = fields["title"].strip()
    if "description" in fields and (not isinstance(fields["description"], str) or len(fields["description"]) > 2000):
        raise ValueError
    if "category" in fields and (not isinstance(fields["category"], str) or fields["category"] not in CATEGORIES):
        raise ValueError
    if "tags" in fields:
        tags = fields["tags"]
        if not isinstance(tags, list) or len(tags) > 5:
            raise ValueError
        normalized = []
        for tag in tags:
            if not isinstance(tag, str) or len(tag) > 64:
                raise ValueError
            tag = tag.strip().removeprefix("#").lower()
            if not re.fullmatch(r"[a-z0-9_]{1,30}", tag):
                raise ValueError
            if tag not in normalized:
                normalized.append(tag)
        fields["tags"] = normalized
    cover = fields.get("cover_time_ms")
    if cover is not None and (type(cover) is not int or not 0 <= cover <= 300_000):
        raise ValueError
    return fields
