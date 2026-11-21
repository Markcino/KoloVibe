"""Plain-text labels; Django retains autoescaping for every returned value."""
from django import template
register = template.Library()


@register.filter
def human_label(value):
    return value.replace("_", " ").replace(".", " / ").capitalize() if isinstance(value, str) else ""
