from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .videos import list_videos, video_detail
from . import accounts
from .creators import creator_detail

from .creator_onboarding import creator_onboarding

if settings.LOCAL_STREAM_ENABLED:
    from .stream_ingest import cloudflare_stream_webhook, issue_video_upload, video_collection, video_playback
else:
    video_collection = list_videos

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("videos", list_videos, name="videos"),
    path("api/v1/videos", video_collection, name="api-videos"),
    path("api/v1/videos/<uuid:video_id>", video_detail, name="api-video-detail"),
    path("api/v1/auth/register", accounts.register, name="register"),
    path("api/v1/auth/verify", accounts.verify_email, name="verify"),
    path("api/v1/auth/login", accounts.login, name="login"),
    path("api/v1/auth/mfa/verify", accounts.verify_mfa, name="mfa-verify"),
    path("api/v1/auth/refresh", accounts.refresh, name="refresh"),
    path("api/v1/auth/logout", accounts.logout, name="logout"),
    path("api/v1/me", accounts.me, name="me"),
    path("api/v1/creators/<uuid:creator_id>", creator_detail, name="api-creator-detail"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]

if settings.ENVIRONMENT == "local":
    from .likes import video_like

    urlpatterns.append(path("api/v1/videos/<uuid:video_id>/like", video_like, name="api-video-like"))
