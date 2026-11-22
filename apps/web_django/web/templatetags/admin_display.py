"""Plain-text labels; Django retains autoescaping for every returned value."""
from datetime import datetime, timezone
from django import template
register = template.Library()


@register.filter
def human_label(value):
    return value.replace("_", " ").replace(".", " / ").capitalize() if isinstance(value, str) else ""


@register.filter
def utc_stamp(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return ""
    if stamp.tzinfo is None:
        return ""
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%d · %H:%M:%S UTC")


TONES = {"review": "pending", "open": "pending", "published": "positive", "resolved": "positive",
         "restored": "positive", "applied": "positive", "active": "pending",
         "rejected": "negative", "removed": "negative", "denied": "negative"}
TONE_ICONS = {"pending": "clock", "positive": "check", "negative": "close", "neutral": "info"}


@register.filter
def status_tone(value):
    return TONES.get(value, "neutral") if isinstance(value, str) else "neutral"


@register.filter
def status_icon(value):
    return TONE_ICONS[status_tone(value)]


@register.filter
def short_id(value):
    return value[:8] if isinstance(value, str) else ""


@register.filter
def age(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return ""
    if stamp.tzinfo is None:
        return ""
    seconds = int((datetime.now(timezone.utc) - stamp).total_seconds())
    if seconds < 60:
        return "Just now"
    for size, unit in ((86400, "d"), (3600, "h"), (60, "min")):
        if seconds >= size:
            return f"{seconds // size} {unit} ago"
