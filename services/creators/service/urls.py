from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .profiles import internal_profile

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
    path("internal/creators/profile", internal_profile, name="internal-profile"),
]
