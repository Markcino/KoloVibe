from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .events import ingest
from .erasure_recovery import erasure_recovery
from .reader import read_events

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/audit/read", read_events),
    path("internal/audit/erasure-recovery", erasure_recovery),
    path("internal/security-events", ingest, name="security-events"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]
