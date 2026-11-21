from uuid import UUID
from datetime import datetime

STATUSES = {"videos": ["review", "published", "rejected", "removed"], "reports": ["open", "resolved", "dismissed"], "appeals": ["open", "denied", "restored"]}


def valid_totals(value):
    return (isinstance(value, dict) and set(value) == set(STATUSES)
            and all(isinstance(value[kind], dict) and set(value[kind]) == set(states)
                and all(type(count) is int and count >= 0 for count in value[kind].values())
                for kind, states in STATUSES.items()))


def valid_holds(value):
    try:
        if (not isinstance(value, dict) or set(value) != {"total", "items", "next_cursor"}
                or type(value["total"]) is not int or value["total"] < 0
                or not isinstance(value["items"], list) or len(value["items"]) > 20 or len(value["items"]) > value["total"]):
            return False
        for item in value["items"]:
            if (set(item) != {"id", "video_id", "reason_code", "created_at"}
                    or str(UUID(item["id"])) != item["id"] or str(UUID(item["video_id"])) != item["video_id"]
                    or not isinstance(item["reason_code"], str) or not 1 <= len(item["reason_code"]) <= 64
                    or datetime.fromisoformat(item["created_at"]).tzinfo is None):
                return False
        ids = [item["id"] for item in value["items"]]
        return ids == sorted(set(ids)) and (value["next_cursor"] is None or len(ids) == 20 and value["next_cursor"] == ids[-1])
    except (ValueError, TypeError, AttributeError, KeyError):
        return False
