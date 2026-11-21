"""Bounded validation for existing R1 gateway contracts before rendering."""

import uuid
from django.utils.dateparse import parse_datetime

QUEUE_STATUS = {"videos": "review", "reports": "open", "appeals": "open"}
ACTIONS = {"videos": {"publish", "reject", "remove"}, "reports": {"dismiss", "remove"},
           "appeals": {"deny", "restore"}}


def valid_id(value):
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _text(value, maximum, minimum=0):
    return isinstance(value, str) and minimum <= len(value) <= maximum


def _timestamp(value):
    if not _text(value, 64, 1):
        return False
    try:
        return parse_datetime(value) is not None
    except ValueError:
        return False


def valid_queue_record(item, kind, selected_status=None):
    fields = ({"id", "title"} if kind == "videos" else
              {"id", "video_id", "status", "created_at", "reason"} | ({"details"} if kind == "reports" else set()))
    if (not isinstance(item, dict) or set(item) != fields or not valid_id(item["id"])
            or not all(isinstance(value, str) for value in item.values())):
        return False
    if kind == "videos":
        return _text(item["title"], 160, 1)
    return (valid_id(item["video_id"]) and item["status"] == (selected_status or "open") and _timestamp(item["created_at"])
            and (_text(item["reason"], 2000, 10) if kind == "appeals" else
                 item["reason"] in {"spam", "harassment", "copyright", "harmful", "other"}
                 and _text(item["details"], 2000)))


def valid_queue_page(page, kind, *, cursor=None, selected_status=None):
    if not isinstance(page, dict) or set(page) != {"items", "next_cursor"}:
        return False
    items = page["items"]
    if not isinstance(items, list) or len(items) > 20 or not all(valid_queue_record(item, kind, selected_status) for item in items):
        return False
    ids = [item["id"] for item in items]
    if ids != sorted(set(ids)) or cursor is not None and any(item_id <= cursor for item_id in ids):
        return False
    next_cursor = page["next_cursor"]
    return next_cursor is None or (valid_id(next_cursor) and len(items) == 20 and next_cursor == ids[-1])


def valid_decision(result, video_id, action):
    return (isinstance(result, dict) and set(result) == {"id", "video_id", "action", "status"}
            and valid_id(result["id"]) and valid_id(result["video_id"])
            and result["video_id"] == video_id
            and result["action"] == action and result["status"] == "applied")


def valid_sessions(payload):
    if not isinstance(payload, dict) or set(payload) != {"items"}:
        return False
    items = payload["items"]
    return (isinstance(items, list) and len(items) <= 40 and all(
        isinstance(item, dict) and set(item) == {"id", "created_at", "expires_at", "current"}
        and valid_id(item["id"]) and type(item["current"]) is bool
        and _timestamp(item["created_at"]) and _timestamp(item["expires_at"])
        for item in items) and len({item["id"] for item in items}) == len(items))
