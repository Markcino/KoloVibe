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

    urlpatterns.append(path("internal/likes", update_like, name="internal-like"))
