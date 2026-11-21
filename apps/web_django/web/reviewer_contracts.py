from datetime import datetime
from uuid import UUID


def valid_detail(value):
    try:
        if not isinstance(value, dict) or set(value) != {"record", "video", "preview", "reports", "decisions", "history_truncated"}:
            return False
        video = value["video"]
        if (set(video) != {"id", "title", "description", "state", "duration_seconds", "rights_status"}
                or str(UUID(video["id"])) != video["id"] or video["rights_status"] != "not_recorded"
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
