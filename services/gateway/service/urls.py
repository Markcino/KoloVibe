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

if settings.ENVIRONMENT == "local" or getattr(settings, "STAGING_CREATOR_ONBOARDING", False):
    urlpatterns += [
        path("api/v1/creator-invitations", creator_onboarding, {"operation": "invite"}, name="creator-invite"),
        path("api/v1/creator-applications", creator_onboarding, {"operation": "pending"}, name="creator-queue"),
        path("api/v1/creator-applications/<uuid:account_id>/decision", creator_onboarding,
             {"operation": "review"}, name="creator-review"),
        path("api/v1/creators/me/application", creator_onboarding,
             {"operation": "application"}, name="creator-application"),
        path("api/v1/creators/me/upload-eligibility", creator_onboarding,
             {"operation": "eligibility"}, name="creator-upload-eligibility"),
    ]

if settings.LOCAL_STREAM_ENABLED:
    urlpatterns += [
        path("api/v1/videos/<uuid:video_id>/upload-intents", issue_video_upload, name="api-video-upload"),
        path("api/v1/videos/<uuid:video_id>/playback", video_playback, name="api-video-playback"),
        path("api/v1/webhooks/cloudflare-stream", cloudflare_stream_webhook, name="api-stream-webhook"),
    ]
