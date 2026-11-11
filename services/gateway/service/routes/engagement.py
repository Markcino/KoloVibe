"""Viewer engagement routes: likes, follows, and the following feed."""
from django.urls import path

from ..capabilities import enabled


def patterns():
    if not enabled("engagement"):
        return []
    from ..following import following_videos
    from ..follows import creator_follow
    from ..likes import video_like
    from ..shares import video_share

    return [
        path("api/v1/videos/<uuid:video_id>/like", video_like, name="api-video-like"),
        path("api/v1/videos/<uuid:video_id>/shares", video_share, name="api-video-share"),
        path("api/v1/creators/<uuid:creator_id>/follow", creator_follow, name="api-creator-follow"),
        path("api/v1/videos/following", following_videos, name="api-following-videos"),
    ]
