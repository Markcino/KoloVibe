"""Strict moderator invitation response shapes; never render extra upstream fields."""

import re
import uuid
from datetime import datetime


def identifier(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def timestamp(value):
    try:
        return isinstance(value, str) and len(value) <= 40 and datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def valid_receipt(value):
    return (isinstance(value, dict) and set(value) == {"id", "status", "expires_at"}
            and identifier(value["id"]) and value["status"] == "pending" and timestamp(value["expires_at"]))


def valid_page(value):
    return (isinstance(value, dict) and set(value) == {"items", "next_cursor"}
            and (value["next_cursor"] is None or identifier(value["next_cursor"]))
            and isinstance(value["items"], list) and len(value["items"]) <= 50
            and all(isinstance(row, dict) and set(row) == {"id", "display_name", "email_masked", "status", "expires_at"}
                    and identifier(row["id"]) and timestamp(row["expires_at"])
                    and isinstance(row["display_name"], str) and 2 <= len(row["display_name"]) <= 80
                    and isinstance(row["email_masked"], str) and 1 <= len(row["email_masked"]) <= 257
                    and row["status"] in ("pending", "expired", "revoked", "accepted") for row in value["items"]))


def valid_setup(value):
    return (isinstance(value, dict) and set(value) == {"secret", "expires_at"}
            and isinstance(value["secret"], str) and re.fullmatch(r"[A-Z2-7]{32}", value["secret"]) is not None
            and timestamp(value["expires_at"]))


def valid_complete(value):
    return (isinstance(value, dict) and set(value) == {"enrolled", "recovery_codes"} and value["enrolled"] is True
            and isinstance(value["recovery_codes"], list) and len(value["recovery_codes"]) == 10
            and all(isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_-]{32,128}", code) for code in value["recovery_codes"])
            and len(set(value["recovery_codes"])) == 10)
