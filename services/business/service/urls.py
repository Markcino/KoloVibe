from django.http import JsonResponse
from django.urls import path

from .health import liveness
from .api import dispatch

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status": "ok"}), name="internal-probe"),
    path("internal/business/<slug:operation>", dispatch, name="internal-business"),
]
