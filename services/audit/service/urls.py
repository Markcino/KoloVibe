from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .events import ingest

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/security-events", ingest, name="security-events"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]
