"""Creator onboarding, own content, upload, playback, and analytics routes."""
from django.urls import path

from ..capabilities import enabled


def patterns():
    routes = []
    if enabled("creator_onboarding"):
        from ..creator_onboarding import creator_onboarding

        routes += [
            path("api/v1/creator-invitations", creator_onboarding, {"operation": "invite"}, name="creator-invite"),
            path("api/v1/creator-applications", creator_onboarding, {"operation": "pending"}, name="creator-queue"),
            path("api/v1/creator-applications/<uuid:account_id>/decision", creator_onboarding,
                 {"operation": "review"}, name="creator-review"),
            path("api/v1/creators/me/application", creator_onboarding,
                 {"operation": "application"}, name="creator-application"),
            path("api/v1/creators/me/upload-eligibility", creator_onboarding,
                 {"operation": "eligibility"}, name="creator-upload-eligibility"),
        ]
    if enabled("media"):
        from ..media import (issue_video_upload, own_video_detail, own_video_library,
                             video_playback, video_upload_status)

        routes += [
            path("api/v1/creators/me/videos", own_video_library, name="api-own-videos"),
            path("api/v1/creators/me/videos/<uuid:video_id>", own_video_detail, name="api-own-video-detail"),
            path("api/v1/videos/<uuid:video_id>/upload-intents", issue_video_upload, name="api-video-upload"),
            path("api/v1/videos/<uuid:video_id>/playback", video_playback, name="api-video-playback"),
            path("api/v1/videos/<uuid:video_id>/upload-status", video_upload_status,
                 name="api-video-upload-status"),
        ]
    if enabled("analytics"):
        from ..analytics import creator_analytics, creator_video_analytics

        routes += [
            path("api/v1/creators/me/analytics", creator_analytics, name="api-creator-analytics"),
            path("api/v1/creators/me/videos/<uuid:video_id>/analytics", creator_video_analytics,
                 name="api-creator-video-analytics"),
        ]
    return routes
