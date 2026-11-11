from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .videos import (list_videos, video_detail, internal_list_videos, internal_video_detail,
                     internal_lookup, internal_published_count)

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("videos", list_videos, name="videos"),
    path("videos/<uuid:video_id>", video_detail, name="video_detail"),
    path("internal/videos", internal_list_videos, name="internal-videos"),
    path("internal/videos/detail", internal_video_detail, name="internal-video-detail"),
    path("internal/videos/lookup", internal_lookup, name="internal-video-lookup"),
    path("internal/videos/published-count", internal_published_count, name="internal-published-count"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]

if settings.LOCAL_MEDIA_ENABLED:
    from .media_api import media_api
    from .analytics import content_analytics

    urlpatterns.append(path("internal/videos/media/<slug:operation>", media_api, name="internal-media"))
    urlpatterns.append(path("internal/videos/analytics/<slug:operation>", content_analytics, name="internal-analytics"))

if settings.LOCAL_MODERATION_ENABLED:
    from .moderation import moderation_video

    urlpatterns.append(path("internal/videos/moderation/<slug:operation>", moderation_video, name="internal-video-moderation"))
