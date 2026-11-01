"""Validate gateway data before passing it to templates or URL reversal."""

import re
import uuid


def valid_id(value):
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


def valid_video(value):
    return (
        isinstance(value, dict)
        and valid_id(value.get("id")) and valid_id(value.get("creator_id"))
        and value.get("state") == "published"
        and isinstance(value.get("title"), str) and 1 <= len(value["title"]) <= 160
        and isinstance(value.get("description"), str) and len(value["description"]) <= 2000
    )


def valid_page(value, *, cursor=None, creator_id=None):
    if not isinstance(value, dict) or set(value) != {"items", "next_cursor"}:
        return False
    items = value["items"]
    if not isinstance(items, list) or len(items) > 20 or not all(map(valid_video, items)):
        return False
    if len({item["id"] for item in items}) != len(items):
        return False
    if creator_id and any(item["creator_id"] != creator_id for item in items):
        return False
    next_cursor = value["next_cursor"]
    return next_cursor is None or (
        valid_id(next_cursor) and len(items) == 20
        and next_cursor == items[-1]["id"] and next_cursor != cursor
    )


def valid_creator(value):
    return (
        isinstance(value, dict)
        and valid_id(value.get("id")) and valid_id(value.get("user_id"))
        and value.get("status") == "active"
        and isinstance(value.get("handle"), str)
        and re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", value["handle"]) is not None
        and isinstance(value.get("bio"), str) and len(value["bio"]) <= 500
    )
