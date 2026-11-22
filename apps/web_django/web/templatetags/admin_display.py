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
