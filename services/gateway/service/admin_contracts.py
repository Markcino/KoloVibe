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


def valid_audit_page(value):
    try:
        if not isinstance(value, dict) or set(value) != {"items", "next_cursor"} or not isinstance(value["items"], list) or len(value["items"]) > 20:
            return False
        order = []
        for item in value["items"]:
            if (not isinstance(item, dict) or set(item) != {"id", "kind", "occurred_at", "producer", "subject_type"}
                    or str(UUID(item["id"])) != item["id"] or not isinstance(item["kind"], str) or not 1 <= len(item["kind"]) <= 64
                    or item["producer"] not in {"identity", "moderation", "creators", "content", "points", "audit", "business"}
                    or item["subject_type"] is not None and (not isinstance(item["subject_type"], str) or len(item["subject_type"]) > 32)):
                return False
            stamp = datetime.fromisoformat(item["occurred_at"])
            if stamp.tzinfo is None:
                return False
            order.append((stamp, item["id"]))
        ids = [item["id"] for item in value["items"]]
        return (len(set(ids)) == len(ids) and order == sorted(order, reverse=True)
                and (value["next_cursor"] is None or len(ids) == 20 and value["next_cursor"] == ids[-1]))
    except (ValueError, TypeError, AttributeError, KeyError):
        return False


def valid_points_review(value):
    try:
        account = "account_id" in value
        fields = {"items", "next_cursor", "as_of"} | ({"account_id", "balance", "currency"} if account else set())
        if not isinstance(value, dict) or set(value) != fields or datetime.fromisoformat(value["as_of"]).tzinfo is None:
            return False
        if account and (str(UUID(value["account_id"])) != value["account_id"] or type(value["balance"]) is not int or value["currency"] != "POINTS"):
            return False
        rows = value["items"]
        if not isinstance(rows, list) or len(rows) > 20:
            return False
        ids = []
        for item in rows:
            if not isinstance(item, dict):
                return False
            if account:
                if (set(item) != {"id", "amount", "kind", "rule_version", "reason_code", "created_at", "reversal_review_state"}
                        or str(UUID(item["id"])) != item["id"] or type(item["amount"]) is not int or item["amount"] == 0
                        or item["kind"] not in {"award", "reversal", "adjustment"}
                        or not isinstance(item["rule_version"], str) or not 1 <= len(item["rule_version"]) <= 32
                        or not isinstance(item["reason_code"], str) or not 1 <= len(item["reason_code"]) <= 64
                        or datetime.fromisoformat(item["created_at"]).tzinfo is None
                        or item["reversal_review_state"] not in {"reversed", "not_reversed", "reversal", "not_applicable"}):
                    return False
                ids.append(item["id"])
            else:
                if (set(item) != {"account_id", "balance", "currency"} or str(UUID(item["account_id"])) != item["account_id"]
                        or type(item["balance"]) is not int or item["currency"] != "POINTS"):
                    return False
                ids.append(item["account_id"])
        return ids == sorted(set(ids)) and (value["next_cursor"] is None or len(ids) == 20 and value["next_cursor"] == ids[-1])
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def valid_assignment_list(value, scope, target):
    try:
        if (not isinstance(value, dict) or set(value) != {"scope", "target_id", "items"}
                or value["scope"] != scope or value["target_id"] != target
                or not isinstance(value["items"], list) or len(value["items"]) > 100):
            return False
        ids = []
        for item in value["items"]:
            if not isinstance(item, dict) or set(item) != {"moderator_id"} or str(UUID(item["moderator_id"])) != item["moderator_id"]:
                return False
            ids.append(item["moderator_id"])
        return ids == sorted(set(ids))
    except (ValueError, TypeError, AttributeError, KeyError):
        return False


def valid_assignment(value, request):
    return (isinstance(value, dict) and set(value) == {"scope", "target_id", "moderator_id", "active"}
            and all(value[key] == request[key] for key in ("scope", "target_id", "moderator_id", "active"))
            and type(value["active"]) is bool)


def valid_assignment_summary(value, requested):
    try:
        if not isinstance(value, dict) or set(value) != {"items"} or not isinstance(value["items"], list):
            return False
        ids = []
        for item in value["items"]:
            if (not isinstance(item, dict) or set(item) != {"moderator_id", "videos", "reports", "appeals"}
                    or str(UUID(item["moderator_id"])) != item["moderator_id"]
                    or any(type(item[key]) is not int or not 0 <= item[key] <= 1_000_000 for key in ("videos", "reports", "appeals"))):
                return False
            ids.append(item["moderator_id"])
        return ids == sorted(requested)
    except (ValueError, TypeError, AttributeError, KeyError):
        return False
