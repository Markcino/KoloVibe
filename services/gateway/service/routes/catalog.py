"""Public catalogue routes: approved videos and reviewed creators."""
from django.http import JsonResponse
from django.urls import path

from ..capabilities import enabled


def patterns():
    from ..creators import creator_detail, search_creators
    from ..health import liveness
    from ..videos import list_videos, video_detail

    video_collection, video_item = list_videos, video_detail
    if enabled("media"):
        from ..media import video_collection, video_item

    return [
        path("health/live", liveness, name="liveness"),
        path("videos", list_videos, name="videos"),
        path("api/v1/videos", video_collection, name="api-videos"),
        path("api/v1/videos/<uuid:video_id>", video_item, name="api-video-detail"),
        path("api/v1/creators/search", search_creators, name="api-creator-search"),
        path("api/v1/creators/<uuid:creator_id>", creator_detail, name="api-creator-detail"),
        path("internal/probe", lambda request: JsonResponse({"status": "ok"}), name="internal-probe"),
    ]
