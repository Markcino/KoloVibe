"""Viewer engagement routes: likes, follows, shares (with their app-link files), and the following feed."""
from django.urls import path

from ..capabilities import enabled


def patterns():
    if not enabled("engagement"):
        return []
    from ..following import following_videos
    from ..follows import creator_follow
    from ..likes import video_like
    from ..shares import video_share
    from ..app_links import android_asset_links, apple_app_site_association, open_video

    return [
        path("api/v1/videos/<uuid:video_id>/like", video_like, name="api-video-like"),
        path("api/v1/videos/<uuid:video_id>/shares", video_share, name="api-video-share"),
        path("api/v1/creators/<uuid:creator_id>/follow", creator_follow, name="api-creator-follow"),
        path("api/v1/videos/following", following_videos, name="api-following-videos"),
        # Owner decision SIM-02: share links open the app; these serve only association files and a store redirect.
        path(".well-known/apple-app-site-association", apple_app_site_association, name="app-link-apple"),
        path(".well-known/assetlinks.json", android_asset_links, name="app-link-android"),
        path("open/videos/<uuid:video_id>", open_video, name="app-link-video"),
    ]
