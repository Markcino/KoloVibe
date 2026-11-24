"""Operating hours: validation and the single 'open now' computation (reused by search in B4)."""
import datetime as dt
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import limits
from .errors import ApiError
from .validation import parse

TIME = re.compile(r"(?:([01]\d|2[0-3]):([0-5]\d)|24:00)")


def _minute(value, *, closing):
    if not isinstance(value, str) or not TIME.fullmatch(value):
        raise ApiError(400, "Invalid request")
    if value == "24:00":
        if not closing:
            raise ApiError(400, "Invalid request")
        return 1440
    return int(value[:2]) * 60 + int(value[3:])


def clock(minute):
    return f"{minute // 60:02d}:{minute % 60:02d}"


def time_zone(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ApiError(400, "Invalid request")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ApiError(400, "Invalid request") from None
    return value


def _date(value):
    try:
        parsed = dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ApiError(400, "Invalid request") from None
    if parsed.isoformat() != value:
        raise ApiError(400, "Invalid request")
    return parsed


def validate(data):
    """Return (rules, exceptions) as minute tuples after rejecting overlap, bad times and duplicates."""
    fields = parse(data, {"rules": (lambda v: v, True), "exceptions": (lambda v: v, False)})
    rules, exceptions = fields["rules"], fields.get("exceptions", [])
    if (not isinstance(rules, list) or len(rules) > limits.MAX_HOURS_RULES
            or not isinstance(exceptions, list) or len(exceptions) > limits.MAX_HOURS_EXCEPTIONS):
        raise ApiError(400, "Invalid request")
    parsed_rules = []
    for item in rules:
        row = parse(item, {"weekday": (lambda v: v, True), "opens": (lambda v: v, True), "closes": (lambda v: v, True)})
        if type(row["weekday"]) is not int or not 0 <= row["weekday"] <= 6:
            raise ApiError(400, "Invalid request")
        opens, closes = _minute(row["opens"], closing=False), _minute(row["closes"], closing=True)
        if opens >= closes:  # an overnight opening is entered as two intervals
            raise ApiError(400, "Invalid request")
        parsed_rules.append((row["weekday"], opens, closes))
    parsed_rules.sort()
    for earlier, later in zip(parsed_rules, parsed_rules[1:]):
        if earlier[0] == later[0] and later[1] < earlier[2]:
            raise ApiError(400, "Invalid request")
    parsed_exceptions, seen = [], set()
    for item in exceptions:
        row = parse(item, {"on_date": (lambda v: v, True), "closed": (lambda v: v, True),
                           "opens": (lambda v: v, False), "closes": (lambda v: v, False)})
        day = _date(row["on_date"])
        if type(row["closed"]) is not bool or day in seen:
            raise ApiError(400, "Invalid request")
        seen.add(day)
        if row["closed"]:
            if "opens" in row or "closes" in row:
                raise ApiError(400, "Invalid request")
            parsed_exceptions.append((day, True, None, None))
        else:
            if "opens" not in row or "closes" not in row:
                raise ApiError(400, "Invalid request")
            opens, closes = _minute(row["opens"], closing=False), _minute(row["closes"], closing=True)
            if opens >= closes:
                raise ApiError(400, "Invalid request")
            parsed_exceptions.append((day, False, opens, closes))
    return parsed_rules, sorted(parsed_exceptions, key=lambda row: row[0])


def is_open(rules, exceptions, zone, now):
    """True/False for the business's local time; None when no hours are recorded (unknown, not closed)."""
    if not rules and not exceptions:
        return None
    local = now.astimezone(ZoneInfo(zone))
    minute = local.hour * 60 + local.minute
    for day, closed, opens, closes in exceptions:
        if day == local.date():
            return (not closed) and opens <= minute < closes
    return any(day == local.weekday() and opens <= minute < closes for day, opens, closes in rules)
