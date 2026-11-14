from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]

if settings.ENVIRONMENT == "local" or "engagement" in getattr(settings, "STAGING_CAPABILITIES", ()):
    from .likes import update_like, read_like
    from .follows import follow_api, followed_creators
    from .analytics import video_engagement, creator_engagement
    from .discovery import discovery
    from .shares import record_share

    urlpatterns.append(path("internal/likes", update_like, name="internal-like"))
    urlpatterns.append(path("internal/likes/status", read_like, name="internal-like-status"))
    urlpatterns.append(path("internal/follows", follow_api, name="internal-follow"))
    urlpatterns.append(path("internal/follows/membership", followed_creators, name="internal-followed-creators"))
    urlpatterns.append(path("internal/engagement/analytics/video", video_engagement, name="internal-video-analytics"))
    urlpatterns.append(path("internal/engagement/analytics/creator", creator_engagement, name="internal-creator-analytics"))
    urlpatterns.append(path("internal/engagement/shares", record_share, name="internal-share"))
    for operation in ("like-counts", "follower-count", "trending"):
        urlpatterns.append(path("internal/engagement/" + operation, discovery, {"operation": operation}))

if settings.LOCAL_POINTS_ENABLED:
    from .watch import watch_api

    urlpatterns.append(path("internal/engagement/watch/<slug:operation>", watch_api))
