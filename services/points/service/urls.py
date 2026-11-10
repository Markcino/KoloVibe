from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]

if settings.LOCAL_POINTS_ENABLED:
    from .pilot_points import points_read

    urlpatterns.append(path("internal/points/<slug:operation>", points_read))
