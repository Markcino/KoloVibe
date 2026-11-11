"""Bounded signed engagement reads; None is the only unavailable result."""

import json
import time
from urllib.error import HTTPError
from uuid import UUID

from .content_client import lookup_public_videos
from .internal_client import signed_internal_request

_TIMEOUT = 2
_TRENDING_PAGES = 20
_TRENDING_SECONDS = 8


def _uuid(value):
    return isinstance(value, str) and str(UUID(value)) == value


def _count(value):
    return type(value) is int and value >= 0


def _post(path, data, *, deadline=None):
    try:
        timeout = min(_TIMEOUT, deadline - time.monotonic()) if deadline is not None else _TIMEOUT
        if timeout <= 0:
            return None
        with signed_internal_request("engagement", path, method="POST", timeout=timeout,
                                     payload=json.dumps(data, separators=(",", ":")).encode()) as response:
            raw = response.read(8193)
            if response.status != 200 or len(raw) > 8192:
                return None
        result = json.loads(raw)
        return result if isinstance(result, dict) else None
    except HTTPError as error:
        error.close()
        return None
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return None


def like_counts(video_ids) -> dict[str, int] | None:
    try:
        if not isinstance(video_ids, list) or len(video_ids) > 50 or not all(_uuid(value) for value in video_ids):
            return None
        ids = list(dict.fromkeys(video_ids))
        if not ids:
            return {}
        result = _post("/internal/engagement/like-counts", {"video_ids": ids})
        if (result is None or set(result) != {"counts"} or not isinstance(result["counts"], dict)
                or set(result["counts"]) != set(ids) or not all(_count(value) for value in result["counts"].values())):
            return None
        return result["counts"]
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
        return None


def follower_count(creator_id) -> int | None:
    try:
        if not _uuid(creator_id):
            return None
        result = _post("/internal/engagement/follower-count", {"creator_id": creator_id})
        if (result is None or set(result) != {"creator_id", "follower_count"}
                or result["creator_id"] != creator_id or not _count(result["follower_count"])):
            return None
        return result["follower_count"]
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
        return None


def trending_video_ids(limit=20) -> list[str] | None:
    """Rank real qualified plays, then verify current publication in Content.

    Hidden/deleted candidates cannot occupy the returned top-public slots. Signed
    ranking cursors keep the seven-day cutoff fixed while scanning candidates.
    Never return a truncated partial result if the scan/time budget is exhausted.
    """
    try:
        if type(limit) is not int or not 1 <= limit <= 50:
            return None
        deadline, cursor, selected, seen, seen_cursors = time.monotonic() + _TRENDING_SECONDS, None, [], set(), set()
        previous = None
        for _ in range(_TRENDING_PAGES):
            result = _post("/internal/engagement/trending", {"limit": 50, "cursor": cursor}, deadline=deadline)
            if (result is None or set(result) != {"items", "next_cursor"}
                    or not isinstance(result["items"], list) or len(result["items"]) > 50):
                return None
            ids, keys = [], []
            for row in result["items"]:
                if (not isinstance(row, dict) or set(row) != {"video_id", "qualified_plays"}
                        or not _uuid(row["video_id"]) or not _count(row["qualified_plays"]) or row["qualified_plays"] == 0):
                    return None
                ids.append(row["video_id"])
                keys.append((-row["qualified_plays"], row["video_id"]))
            if (keys != sorted(keys) or len(set(ids)) != len(ids) or seen.intersection(ids)
                    or previous is not None and keys and keys[0] <= previous):
                return None
            next_cursor = result["next_cursor"]
            if next_cursor is not None and (not isinstance(next_cursor, str) or not 1 <= len(next_cursor) <= 2048
                    or len(ids) != 50 or next_cursor in seen_cursors):
                return None
            if time.monotonic() >= deadline:
                return None
            items = lookup_public_videos(ids)
            if items is None or time.monotonic() >= deadline:
                return None
            # The existing Content client validates public visibility, item fields
            # and order. It returns only the currently published subset.
            selected.extend(item["id"] for item in items)
            if len(selected) >= limit:
                return selected[:limit]
            if next_cursor is None:
                return selected
            seen.update(ids)
            seen_cursors.add(next_cursor)
            previous, cursor = keys[-1], next_cursor
        return None
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
        return None
