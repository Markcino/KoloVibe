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


@register.filter
def age(value):
    """Relative age such as "3 days ago"; the exact UTC time stays available in the title attribute."""
    from django.utils import timezone
    from django.utils.timesince import timesince
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return ""
    if stamp.tzinfo is None:
        return ""
    if stamp >= timezone.now():
        return "just now"
    return timesince(stamp).split(",")[0].replace("\xa0", " ") + " ago"


@register.filter
def utc_clock(value):
    """HH:MM UTC for an ISO timestamp, e.g. when the signed-in session ends."""
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return ""
    return stamp.astimezone(timezone.utc).strftime("%H:%M UTC") if stamp.tzinfo else ""
