"""Exact validators for the Business reviewer and administrator operations the console calls (DOC-205).

The console never renders, or acts on, a gateway body it has not shape-checked: an extra field, a wrong type, an
out-of-bounds value or an id that is not the one asked for makes the page fail closed. Text fields are only length-
and type-checked here; they are rendered by Django's auto-escaping and are never marked safe.
"""

import re
from datetime import datetime
from uuid import UUID

CODE = re.compile(r"[a-z][a-z_]{2,39}")
SLUG = re.compile(r"[a-z0-9-]{2,60}")
EVIDENCE_KIND = CODE

VERIFICATION_STATES = {"submitted", "under_review", "needs_info", "verified", "rejected", "revoked"}
BUSINESS_STATES = {"draft", "submitted", "under_review", "needs_info", "verified", "rejected", "suspended", "revoked", "closed"}
REVISION_STATES = {"draft", "pending_review", "approved", "rejected", "superseded"}
SUBJECT_TYPES = {"review", "review_response", "inquiry_message"}
SCOPES = {"verification", "profile_review", "review_queue"}

# decision -> (case state, business state) the backend answers with; anything else is not trusted.
VERIFICATION_OUTCOME = {"verify": ("verified", "verified"), "reject": ("rejected", "rejected"),
                        "request_info": ("needs_info", "needs_info"), "revoke": ("revoked", "revoked")}
VERIFICATION_DECISIONS = tuple(VERIFICATION_OUTCOME)
PROFILE_DECISIONS = {"approve": "approved", "reject": "rejected"}
REPORT_DECISIONS = ("keep", "remove")


def _id(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def _text(value, low, high):
    return isinstance(value, str) and low <= len(value) <= high


def _stamp(value):
    try:
        return isinstance(value, str) and datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _page(value, keys, valid_item, id_key, cursor=None):
    """A keyset page: bounded, ascending by id, strictly after the cursor, with a cursor that can only move forward.

    Reviewer queues may hide rows the caller is conflicted on after paging, so `next_cursor` can name an id that is
    not in `items`; it must still be a valid id past the last row shown.
    """
    try:
        if not isinstance(value, dict) or set(value) != {"items", "next_cursor"} or not isinstance(value["items"], list):
            return False
        items = value["items"]
        if len(items) > 20 or not all(isinstance(item, dict) and set(item) == keys and valid_item(item) for item in items):
            return False
        ids = [item[id_key] for item in items]
        if ids != sorted(set(ids)) or cursor is not None and not all(i > cursor for i in ids):
            return False
        following = value["next_cursor"]
        return following is None or (_id(following) and (not ids or following >= ids[-1]) and following != cursor)
    except (TypeError, KeyError):
        return False


def valid_verification_queue(value, cursor=None):
    return _page(value, {"case_id", "business_id", "display_name", "state", "submitted_at", "assigned_to_you"},
                 lambda i: _id(i["case_id"]) and _id(i["business_id"]) and _text(i["display_name"], 1, 80)
                 and i["state"] in {"submitted", "under_review"} and _stamp(i["submitted_at"])
                 and type(i["assigned_to_you"]) is bool, "case_id", cursor)


def valid_profile_queue(value, cursor=None):
    return _page(value, {"revision_id", "business_id", "display_name", "submitted_at"},
                 lambda i: _id(i["revision_id"]) and _id(i["business_id"]) and _text(i["display_name"], 1, 80)
                 and _stamp(i["submitted_at"]), "revision_id", cursor)


def valid_report_queue(value, cursor=None):
    return _page(value, {"report_id", "subject_type", "business_id", "reason_code", "system_hold", "created_at"},
                 lambda i: _id(i["report_id"]) and i["subject_type"] in SUBJECT_TYPES and _id(i["business_id"])
                 and _text(i["reason_code"], 1, 64) and type(i["system_hold"]) is bool and _stamp(i["created_at"]),
                 "report_id", cursor)


def valid_verification_case(value, case_id):
    try:
        if (not isinstance(value, dict) or set(value) != {
                "case_id", "business_id", "state", "method", "display_name", "legal_name", "submitted_at",
                "assigned_to_you", "evidence", "duplicate_candidates"}
                or value["case_id"] != case_id or not _id(value["business_id"]) or value["state"] not in VERIFICATION_STATES
                or not isinstance(value["method"], str) or not CODE.fullmatch(value["method"])
                or not _text(value["display_name"], 1, 80) or not _text(value["legal_name"], 1, 160)
                or not _stamp(value["submitted_at"]) or type(value["assigned_to_you"]) is not bool
                or not isinstance(value["evidence"], list) or len(value["evidence"]) > 50
                or not isinstance(value["duplicate_candidates"], list) or len(value["duplicate_candidates"]) > 10):
            return False
        for item in value["evidence"]:
            if (not isinstance(item, dict) or set(item) != {"id", "kind", "value"} or not _id(item["id"])
                    or not isinstance(item["kind"], str) or not EVIDENCE_KIND.fullmatch(item["kind"])
                    or not _text(item["value"], 1, 300)):
                return False
        for item in value["duplicate_candidates"]:
            if (not isinstance(item, dict) or set(item) != {"business_id", "display_name", "state"}
                    or not _id(item["business_id"]) or not _text(item["display_name"], 1, 80)
                    or item["state"] not in BUSINESS_STATES):
                return False
        return True
    except (TypeError, KeyError):
        return False


def valid_claim(value, case_id):
    return (isinstance(value, dict) and set(value) == {"case_id", "state"} and value["case_id"] == case_id
            and value["state"] == "under_review")


def valid_verification_decision(value, case_id, decision):
    case_state, business_state = VERIFICATION_OUTCOME[decision]
    return (isinstance(value, dict) and set(value) == {"case_id", "state", "business_state"}
            and value["case_id"] == case_id and value["state"] == case_state and value["business_state"] == business_state)


def valid_profile_revision(value, revision_id):
    try:
        keys = {"business_id", "id", "revision_no", "state", "display_name", "category", "description", "county_code",
                "city", "address_line", "address_public", "latitude", "longitude", "coordinates_public", "time_zone",
                "contacts", "reason_code", "changed_fields"}
        if (not isinstance(value, dict) or set(value) != keys or value["id"] != revision_id or not _id(value["business_id"])
                or type(value["revision_no"]) is not int or value["revision_no"] < 1 or value["state"] not in REVISION_STATES
                or not _text(value["display_name"], 1, 80) or value["category"] is not None and not _text(value["category"], 1, 60)
                or not _text(value["description"], 0, 2000) or not _text(value["county_code"], 0, 40)
                or not _text(value["city"], 0, 80) or not _text(value["address_line"], 0, 200)
                or type(value["address_public"]) is not bool or type(value["coordinates_public"]) is not bool
                or any(value[k] is not None and not _text(value[k], 1, 24) for k in ("latitude", "longitude"))
                or not _text(value["time_zone"], 1, 64) or value["reason_code"] is not None and not _text(value["reason_code"], 1, 40)
                or not isinstance(value["contacts"], list) or len(value["contacts"]) > 10
                or not isinstance(value["changed_fields"], list) or len(value["changed_fields"]) > 30
                or not all(_text(name, 1, 40) for name in value["changed_fields"])):
            return False
        return all(isinstance(c, dict) and set(c) == {"kind", "value", "is_public"} and _text(c["kind"], 1, 16)
                   and _text(c["value"], 1, 300) and type(c["is_public"]) is bool for c in value["contacts"])
    except (TypeError, KeyError):
        return False


def valid_profile_decision(value, revision_id, decision):
    return (isinstance(value, dict) and set(value) == {"revision_id", "state"} and value["revision_id"] == revision_id
            and value["state"] == PROFILE_DECISIONS[decision])


def valid_report_case(value, report_id):
    try:
        if (not isinstance(value, dict) or set(value) != {"report_id", "subject_type", "subject_id", "business_id",
                                                         "reason_code", "details", "system_hold", "content"}
                or value["report_id"] != report_id or value["subject_type"] not in SUBJECT_TYPES
                or not _id(value["subject_id"]) or not _id(value["business_id"]) or not _text(value["reason_code"], 1, 64)
                or not isinstance(value["details"], str) or len(value["details"]) > 2000 or type(value["system_hold"]) is not bool):
            return False
        content = value["content"]
        if content is None:
            return True
        if not isinstance(content, dict):
            return False
        if value["subject_type"] == "review":
            return (set(content) == {"rating", "title", "body", "state", "basis", "hold_reasons"}
                    and type(content["rating"]) is int and 1 <= content["rating"] <= 5
                    and (content["title"] is None or _text(content["title"], 1, 100)) and _text(content["body"], 0, 2000)
                    and _text(content["state"], 1, 24) and _text(content["basis"], 1, 32)
                    and isinstance(content["hold_reasons"], list) and len(content["hold_reasons"]) <= 10
                    and all(_text(code, 1, 40) for code in content["hold_reasons"]))
        if value["subject_type"] == "review_response":
            return set(content) == {"body", "removed"} and _text(content["body"], 0, 1000) and type(content["removed"]) is bool
        return (set(content) == {"body", "author_kind", "removed"} and _text(content["body"], 0, 1000)
                and content["author_kind"] in {"customer", "business"} and type(content["removed"]) is bool)
    except (TypeError, KeyError):
        return False


def valid_report_decision(value, report_id, decision):
    return (isinstance(value, dict) and set(value) == {"report_id", "state", "decision"}
            and value["report_id"] == report_id and value["state"] == "decided" and value["decision"] == decision)


def valid_category(value):
    return (isinstance(value, dict) and set(value) == {"slug", "name", "active", "parent"}
            and isinstance(value["slug"], str) and SLUG.fullmatch(value["slug"]) is not None
            and _text(value["name"], 2, 80) and type(value["active"]) is bool
            and (value["parent"] is None or isinstance(value["parent"], str) and SLUG.fullmatch(value["parent"]) is not None))


def valid_category_list(value):
    try:
        if not isinstance(value, dict) or set(value) != {"items"} or not isinstance(value["items"], list) or len(value["items"]) > 500:
            return False
        slugs = [item["slug"] for item in value["items"]]
        return all(valid_category(item) for item in value["items"]) and slugs == sorted(set(slugs))
    except (TypeError, KeyError):
        return False


def valid_reviewer_grant(value, scope, active):
    return (isinstance(value, dict) and set(value) == {"id", "scope", "active"} and _id(value["id"])
            and value["scope"] == scope and value["active"] is active)


def valid_registration_grant(value, account_id, active):
    return (isinstance(value, dict) and set(value) == {"account_id", "active"} and value["account_id"] == account_id
            and value["active"] is active)
