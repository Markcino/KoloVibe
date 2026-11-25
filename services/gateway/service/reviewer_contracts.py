from datetime import datetime
import re
from uuid import UUID

RIGHTS_STATUSES = {"attested", "flagged", "claimed", "removed", "restored"}


def valid_detail(value):
    try:
        if not isinstance(value, dict) or set(value) != {"record", "video", "preview", "copyright", "reports", "decisions", "history_truncated"}:
            return False
        if not valid_copyright_context(value["copyright"]):
            return False
        video = value["video"]
        if (set(video) != {"id", "title", "description", "state", "duration_seconds", "rights_status"}
                or str(UUID(video["id"])) != video["id"] or video["rights_status"] not in RIGHTS_STATUSES
                or not isinstance(video["title"], str) or not 1 <= len(video["title"]) <= 160
                or not isinstance(video["description"], str) or len(video["description"]) > 2000
                or video["state"] not in {"draft", "uploading", "processing", "failed", "review", "published", "rejected", "removed"}
                or video["duration_seconds"] is not None and (type(video["duration_seconds"]) is not int or not 0 < video["duration_seconds"] <= 300)):
            return False
        record = value["record"]
        if not isinstance(record, dict) or str(UUID(record["id"])) != record["id"]:
            return False
        if set(record) not in ({"id", "title"}, {"id", "video_id", "status", "created_at", "reason"},
                               {"id", "video_id", "status", "created_at", "reason", "details"}):
            return False
        if set(record) == {"id", "title"} and (record["id"] != video["id"] or record["title"] != video["title"]):
            return False
        if not all(isinstance(item, str) and len(item) <= 2000 for item in record.values()):
            return False
        if "video_id" in record and record["video_id"] != video["id"]:
            return False
        for kind, fields in (("reports", {"id", "video_id", "status", "created_at", "reason", "details"}),
                             ("decisions", {"id", "action", "status", "reason", "created_at"})):
            rows = value[kind]
            if not isinstance(rows, list) or len(rows) > 20:
                return False
            for row in rows:
                if not isinstance(row, dict) or set(row) != fields or not all(isinstance(item, str) and len(item) <= 2000 for item in row.values()):
                    return False
                UUID(row["id"])
                if datetime.fromisoformat(row["created_at"]).tzinfo is None:
                    return False
                if kind == "reports" and row["video_id"] != video["id"]:
                    return False
        if set(value["history_truncated"]) != {"reports", "decisions"} or any(type(item) is not bool for item in value["history_truncated"].values()):
            return False
        preview = value["preview"]
        if preview is not None:
            if (set(preview) != {"id", "url", "expires_at"} or str(UUID(preview["id"])) != preview["id"]
                    or preview["url"] != "/api/v1/moderation/previews/" + preview["id"]
                    or datetime.fromisoformat(preview["expires_at"]).tzinfo is None):
                return False
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


COPYRIGHT_FIELDS = {"work_reference", "claimant_verified", "organisation", "claimant_claims", "claimant_dismissed",
                    "creator_active_strikes"}


def valid_copyright_context(value):
    """Decision E: reviewer-only signals on a copyright record. It never carries the claimant's identity."""
    if value is None:
        return True
    try:
        counts = [value[name] for name in ("claimant_claims", "claimant_dismissed", "creator_active_strikes")]
        return (isinstance(value, dict) and set(value) == COPYRIGHT_FIELDS
                and type(value["claimant_verified"]) is bool
                and (value["work_reference"] is None or isinstance(value["work_reference"], str)
                     and 1 <= len(value["work_reference"]) <= 500)
                and (value["organisation"] is None or isinstance(value["organisation"], str)
                     and 1 <= len(value["organisation"]) <= 200)
                and (value["organisation"] is None or value["claimant_verified"])
                and all(count is None or type(count) is int and 0 <= count <= 1_000_000 for count in counts)
                and (value["claimant_claims"] is None) == (value["claimant_dismissed"] is None)
                and (value["claimant_claims"] is None or value["claimant_dismissed"] <= value["claimant_claims"]))
    except (TypeError, KeyError):
        return False


EDIT_FIELDS = {"title", "description", "category", "tags"}
EDIT_STATUSES = {"pending", "approved", "rejected", "superseded", "withdrawn"}
CATEGORIES = {"hipco", "afrobeats", "comedy", "skits", "short_films", "culture", "documentaries"}
VIDEO_STATES = {"draft", "uploading", "processing", "failed", "review", "published", "rejected", "removed"}


def valid_edit_values(values):
    return (isinstance(values, dict) and set(values) == EDIT_FIELDS
            and isinstance(values["title"], str) and 1 <= len(values["title"]) <= 160
            and isinstance(values["description"], str) and len(values["description"]) <= 2000
            and (values["category"] is None or values["category"] in CATEGORIES)
            and isinstance(values["tags"], list) and len(values["tags"]) <= 5
            and all(isinstance(tag, str) and re.fullmatch(r"[a-z0-9_]{1,30}", tag) for tag in values["tags"]))


def valid_edit_detail(value):
    """Decision A: a held edit, its live and proposed text, and this reviewer's decisions."""
    try:
        if not isinstance(value, dict) or set(value) != {"edit", "decisions"}:
            return False
        edit = value["edit"]
        if (set(edit) != {"id", "video_id", "status", "submitted_at", "video_state", "live", "proposed"}
                or str(UUID(edit["id"])) != edit["id"] or str(UUID(edit["video_id"])) != edit["video_id"]
                or edit["status"] not in EDIT_STATUSES or edit["video_state"] not in VIDEO_STATES
                or datetime.fromisoformat(edit["submitted_at"]).tzinfo is None
                or not valid_edit_values(edit["live"]) or not valid_edit_values(edit["proposed"])):
            return False
        rows = value["decisions"]
        if not isinstance(rows, list) or len(rows) > 20:
            return False
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"id", "action", "status", "reason", "created_at"}
                    or not all(isinstance(item, str) and len(item) <= 2000 for item in row.values())
                    or row["action"] not in {"approve", "reject"} or row["status"] not in {"pending", "applied", "conflict"}):
                return False
            UUID(row["id"])
            if datetime.fromisoformat(row["created_at"]).tzinfo is None:
                return False
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
