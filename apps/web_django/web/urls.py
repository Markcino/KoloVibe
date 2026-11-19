from django.urls import path
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import views

urlpatterns = [
    path("health/live", require_GET(lambda request: JsonResponse({"status": "ok"})), name="web-liveness"),
    path("static/<path:asset>", views.static_asset, name="web-static"),
    path("", views.feed, name="feed"),
    path("videos/<uuid:video_id>/", views.video, name="video"),
    path("creators/<uuid:creator_id>/", views.creator_detail, name="creator-detail"),
    path("register/", views.register, name="register"),
    path("verify/", views.verify, name="verify"),
    path("password/reset-request/", views.password_reset_request, name="password-reset-request"),
    path("password/reset/", views.password_reset, name="password-reset"),
    path("login/", views.login, name="login"),
    path("account/", views.account, name="account"),
    path("account/profile/", views.profile_edit, name="profile-edit"),
    path("account/password/", views.password_change, name="password-change"),
    path("account/sessions/", views.sessions, name="sessions"),
    path("account/sessions/<uuid:session_id>/revoke/", views.revoke_session, name="revoke-session"),
    path("account/preferences/", views.preferences, name="preferences"),
    path("account/privacy/", views.privacy_requests, name="privacy-requests"),
    path("logout/", views.logout, name="logout"),
    path("creator/", views.gated_creator, name="creator"),
    path("points/", views.points, name="points"),
]
