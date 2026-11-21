from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .profiles import internal_profile, internal_search, own_profile
from .onboarding import eligibility, onboarding, ownership

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
    path("internal/creators/search", internal_search, name="internal-search"),
    path("internal/creators/profile", internal_profile, name="internal-profile"),
    path("internal/creators/me", own_profile, name="internal-own-profile"),
]

if settings.ENVIRONMENT == "local" or getattr(settings, "STAGING_CREATOR_ONBOARDING", False):
    urlpatterns.append(path("internal/creators/onboarding/<slug:operation>", onboarding, name="internal-onboarding"))
elif "media" in getattr(settings, "STAGING_CAPABILITIES", frozenset()):
    # Approved `media` capability: only the exact eligibility and ownership operations, each fixed by its route
    # (never taken from the URL), so no other onboarding operation is reachable without the onboarding flag.
    urlpatterns.append(path("internal/creators/onboarding/eligibility", eligibility, name="internal-eligibility"))
    urlpatterns.append(path("internal/creators/onboarding/ownership", ownership, name="internal-ownership"))
    urlpatterns.append(path("internal/creators/onboarding/review_policy", lambda request: onboarding(request, "review_policy")))
