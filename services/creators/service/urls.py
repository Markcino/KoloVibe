from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .profiles import internal_profile
from .onboarding import onboarding

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
    path("internal/creators/profile", internal_profile, name="internal-profile"),
]

if settings.ENVIRONMENT == "local" or getattr(settings, "STAGING_CREATOR_ONBOARDING", False):
    urlpatterns.append(path("internal/creators/onboarding/<slug:operation>", onboarding, name="internal-onboarding"))
