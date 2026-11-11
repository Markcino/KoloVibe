from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]

if settings.ENVIRONMENT == "local":
    from .likes import update_like
    from .follows import follow_api, followed_creators

    urlpatterns.append(path("internal/likes", update_like, name="internal-like"))
    urlpatterns.append(path("internal/follows", follow_api, name="internal-follow"))
    urlpatterns.append(path("internal/follows/membership", followed_creators, name="internal-followed-creators"))

if settings.LOCAL_POINTS_ENABLED:
    from .watch import watch_api

    urlpatterns.append(path("internal/engagement/watch/<slug:operation>", watch_api))
