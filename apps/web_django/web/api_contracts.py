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


def valid_points_balance(value):
    return (
        isinstance(value, dict) and set(value) == {"creator_id", "balance", "currency", "as_of"}
        and valid_id(value["creator_id"]) and type(value["balance"]) is int
        and value["currency"] == "POINTS" and isinstance(value["as_of"], str)
    )


def valid_points_page(value, creator_id, cursor=None):
    if not isinstance(value, dict) or set(value) != {"items", "next_cursor"}:
        return False
    items = value["items"]
    if not isinstance(items, list) or len(items) > 20:
        return False
    for entry in items:
        if (not isinstance(entry, dict)
                or set(entry) != {"id", "creator_id", "amount", "kind", "rule_version", "created_at"}
                or not valid_id(entry["id"]) or entry["creator_id"] != creator_id
                or type(entry["amount"]) is not int
                or entry["kind"] not in {"award", "reversal", "adjustment"}
                or not isinstance(entry["rule_version"], str)
                or not isinstance(entry["created_at"], str)):
            return False
    next_cursor = value["next_cursor"]
    return next_cursor is None or (
        len(items) == 20 and next_cursor == items[-1]["id"] and next_cursor != cursor
    )
