from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .videos import list_videos, video_detail, internal_list_videos, internal_video_detail

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("videos", list_videos, name="videos"),
    path("videos/<uuid:video_id>", video_detail, name="video_detail"),
    path("internal/videos", internal_list_videos, name="internal-videos"),
    path("internal/videos/detail", internal_video_detail, name="internal-video-detail"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]

if settings.LOCAL_STREAM_ENABLED:
    from .stream_ingest import stream_ingest

    urlpatterns.append(path("internal/videos/stream/<slug:operation>", stream_ingest, name="internal-stream-ingest"))
