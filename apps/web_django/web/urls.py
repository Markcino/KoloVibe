from django.urls import path

from . import views

urlpatterns = [
    path("", views.feed, name="feed"),
    path("videos/<uuid:video_id>/", views.video, name="video"),
    path("creators/<uuid:creator_id>/", views.creator_detail, name="creator-detail"),
    path("register/", views.register, name="register"),
    path("verify/", views.verify, name="verify"),
    path("login/", views.login, name="login"),
    path("account/", views.account, name="account"),
    path("logout/", views.logout, name="logout"),
    path("creator/", views.gated_creator, name="creator"),
    path("points/", views.points, name="points"),
]
