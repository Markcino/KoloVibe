"""Route capability gates.

Local development uses explicit local flags. Staging opens a capability only when
the reviewed staging approval configuration lists it; every capability is closed
by default and production remains unauthorized.
"""
from django.conf import settings

CAPABILITIES = frozenset({
    "audit_read",
    "creator_onboarding",
    "media",
    "analytics",
    "moderation",
    "engagement",
    "points",
    "watch",
})


def _local(name):
    media = getattr(settings, "LOCAL_MEDIA_ENABLED", False)
    points = getattr(settings, "LOCAL_POINTS_ENABLED", False)
    return {
        "audit_read": True,
        "creator_onboarding": True,
        "media": media,
        "analytics": media,
        "moderation": getattr(settings, "LOCAL_MODERATION_ENABLED", False),
        "engagement": True,
        "points": points,
        "watch": points and media,
    }[name]


def enabled(name):
    if name not in CAPABILITIES:
        raise ValueError("Unknown capability")
    environment = getattr(settings, "ENVIRONMENT", None)
    if environment == "local":
        return _local(name)
    if environment != "staging":
        return False
    if name == "creator_onboarding" and getattr(settings, "STAGING_CREATOR_ONBOARDING", False):
        return True
    return name in getattr(settings, "STAGING_CAPABILITIES", frozenset())
