from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness
from .videos import list_videos, video_detail
from . import accounts
from .preferences_privacy import preferences, privacy_requests
from .creators import creator_detail, search_creators

from .creator_onboarding import creator_onboarding

if settings.LOCAL_MEDIA_ENABLED:
    from .media import (issue_video_upload, own_video_library, own_video_detail,
                        video_collection, video_item, video_playback, video_upload_status)
else:
    video_collection = list_videos
    video_item = video_detail

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("videos", list_videos, name="videos"),
    path("api/v1/videos", video_collection, name="api-videos"),
    path("api/v1/videos/<uuid:video_id>", video_item, name="api-video-detail"),
    path("api/v1/auth/register", accounts.register, name="register"),
    path("api/v1/auth/verification/resend", accounts.resend_verification, name="verification-resend"),
    path("api/v1/auth/verify", accounts.verify_email, name="verify"),
    path("api/v1/auth/password/reset-request", accounts.request_password_reset, name="reset-request"),
    path("api/v1/auth/password/reset", accounts.reset_password, name="reset-password"),
    path("api/v1/auth/login", accounts.login, name="login"),
    path("api/v1/auth/mfa/verify", accounts.verify_mfa, name="mfa-verify"),
    path("api/v1/auth/refresh", accounts.refresh, name="refresh"),
    path("api/v1/auth/logout", accounts.logout, name="logout"),
    path("api/v1/me/sessions", accounts.sessions, name="account-sessions"),
    path("api/v1/me/password", accounts.change_password, name="change-password"),
    path("api/v1/me/preferences", preferences, name="account-preferences"),
    path("api/v1/me/privacy-requests", privacy_requests, name="account-privacy-requests"),
    path("api/v1/me/sessions/<uuid:session_id>", accounts.revoke_session, name="revoke-account-session"),
    path("api/v1/me", accounts.me, name="me"),
    path("api/v1/creators/search", search_creators, name="api-creator-search"),
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

if settings.LOCAL_MEDIA_ENABLED:
    urlpatterns += [
        path("api/v1/creators/me/videos", own_video_library, name="api-own-videos"),
        path("api/v1/creators/me/videos/<uuid:video_id>", own_video_detail, name="api-own-video-detail"),
        path("api/v1/videos/<uuid:video_id>/upload-intents", issue_video_upload, name="api-video-upload"),
        path("api/v1/videos/<uuid:video_id>/playback", video_playback, name="api-video-playback"),
        path("api/v1/videos/<uuid:video_id>/upload-status", video_upload_status, name="api-video-upload-status"),
    ]

    if settings.ENVIRONMENT == "local":
        from .analytics import creator_analytics, creator_video_analytics

        urlpatterns += [
            path("api/v1/creators/me/analytics", creator_analytics, name="api-creator-analytics"),
            path("api/v1/creators/me/videos/<uuid:video_id>/analytics", creator_video_analytics,
                 name="api-creator-video-analytics"),
        ]

if settings.LOCAL_MODERATION_ENABLED:
    from .moderation import moderation_endpoint

    urlpatterns += [
        path("api/v1/reports", moderation_endpoint, {"operation": "report"}, name="submit-video-report"),
        path("api/v1/me/reports", moderation_endpoint, {"operation": "own_reports"}, name="own-reports"),
        path("api/v1/me/reports/<uuid:target_id>", moderation_endpoint,
             {"operation": "own_report"}, name="own-report-detail"),
        path("api/v1/me/appeals", moderation_endpoint, {"operation": "own_appeals"}, name="own-appeals"),
        path("api/v1/me/appeals/<uuid:target_id>", moderation_endpoint,
             {"operation": "own_appeal"}, name="own-appeal-detail"),
        path("api/v1/videos/<uuid:target_id>/appeals", moderation_endpoint,
             {"operation": "appeal"}, name="submit-video-appeal"),
        path("api/v1/moderation/videos", moderation_endpoint, {"operation": "review_queue"}, name="review-video-queue"),
        path("api/v1/moderation/reports", moderation_endpoint, {"operation": "reports"}, name="moderation-reports"),
        path("api/v1/moderation/appeals", moderation_endpoint, {"operation": "appeals"}, name="moderation-appeals"),
        path("api/v1/moderation/videos/<uuid:target_id>/decisions", moderation_endpoint,
             {"operation": "video_decision"}, name="decide-video"),
        path("api/v1/moderation/reports/<uuid:target_id>/decisions", moderation_endpoint,
             {"operation": "report_decision"}, name="decide-video-report"),
        path("api/v1/moderation/appeals/<uuid:target_id>/decisions", moderation_endpoint,
             {"operation": "appeal_decision"}, name="decide-video-appeal"),
    ]


if settings.ENVIRONMENT == "local":
    from .likes import video_like
    from .follows import creator_follow
    from .following import following_videos

    urlpatterns.append(path("api/v1/videos/<uuid:video_id>/like", video_like, name="api-video-like"))
    urlpatterns.append(path("api/v1/creators/<uuid:creator_id>/follow", creator_follow, name="api-creator-follow"))
    urlpatterns.append(path("api/v1/videos/following", following_videos, name="api-following-videos"))


if settings.LOCAL_POINTS_ENABLED:
    from .pilot_points import creator_points, watch

    urlpatterns += [
        path("api/v1/creators/me/points", creator_points, {"operation": "balance"}, name="creator-points"),
        path("api/v1/creators/me/points/entries", creator_points, {"operation": "entries"}, name="creator-points-entries"),
    ]
    if settings.LOCAL_MEDIA_ENABLED:
        urlpatterns += [
            path("api/v1/videos/<uuid:video_id>/watch-sessions", watch, name="create-watch-session"),
            path("api/v1/engagement/watch-events", watch, name="submit-watch-progress"),
        ]
