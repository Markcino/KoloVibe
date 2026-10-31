from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .videos import list_videos, video_detail

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("videos", list_videos, name="videos"),
    path("videos/<uuid:video_id>", video_detail, name="video_detail"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]
