"""Allowlist field validation: unknown fields, wrong types, control characters and out-of-bounds values are 400."""
import re
import unicodedata
from uuid import UUID

from .errors import ApiError

CODE = re.compile(r"[a-z][a-z_]{2,39}")


def invalid(detail="Invalid request"):
    return ApiError(400, detail)


def clean_text(value, minimum, maximum, *, multiline=False):
    if not isinstance(value, str):
        raise invalid()
    value = unicodedata.normalize("NFC", value).strip()
    if not minimum <= len(value) <= maximum:
        raise invalid()
    for char in value:
        code = ord(char)
        if 0xD800 <= code <= 0xDFFF or (code < 32 and not (multiline and char in "\n\r\t")) or code == 127:
            raise invalid()
    return value


def uuid_text(value):
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise invalid() from None
    if str(parsed) != value:
        raise invalid()
    return parsed


def code_text(value):
    """A reason, evidence or subject code: lower-case words joined by underscores, 3 to 40 characters."""
    if not isinstance(value, str) or not CODE.fullmatch(value):
        raise invalid()
    return value


def boolean(value):
    if type(value) is not bool:
        raise invalid()
    return value


def parse(data, fields):
    """`fields` maps name -> (validator, required). Returns validated values; extra or missing fields raise 400."""
    if not isinstance(data, dict) or set(data) - set(fields):
        raise invalid()
    missing = [name for name, (_, required) in fields.items() if required and name not in data]
    if missing:
        raise invalid()
    return {name: fields[name][0](value) for name, value in data.items()}


def page_params(data, page_size):
    """Shared cursor/limit handling: opaque-to-clients UUID cursor and a bounded page size."""
    cursor = data.get("cursor")
    limit = data.get("limit", page_size)
    if cursor is not None:
        cursor = uuid_text(cursor)
    if isinstance(limit, str):
        if not limit.isdigit() or len(limit) > 3:
            raise invalid()
        limit = int(limit)
    if type(limit) is not int or not 1 <= limit <= page_size:
        raise invalid()
    return cursor, limit


# The cursor/limit pair every paged operation accepts, for `parse(data, PAGE)`.
PAGE = {"cursor": (lambda v: v, False), "limit": (lambda v: v, False)}
