from django.urls import path
from django.views.generic import RedirectView
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import views
from . import invitation_views
from . import assignment_views
from . import business_views
from . import creator_views
from . import edit_views
from . import restriction_views
from . import rights_holder_views

handler400 = views.error_400
handler403 = views.error_403
handler404 = views.error_404
handler500 = views.error_500

urlpatterns = [
    path("health/live", require_GET(lambda request: JsonResponse({"status": "ok"})), name="web-liveness"),
    path("static/<path:asset>", views.static_asset, name="web-static"),
    path("", views.root, name="root"),
    # Natural addresses people try; the console itself lives under /admin/.
    path("moderator/", RedirectView.as_view(pattern_name="dashboard"), name="moderator-home"),
    path("dashboard/", RedirectView.as_view(pattern_name="dashboard"), name="dashboard-alias"),
    path("login/", views.login, name="login"),
    path("login/mfa/", views.login_mfa, name="login-mfa"),
    path("moderator-invitation/", invitation_views.accept, name="moderator-invitation"),
    path("moderator-invitation/qr/", invitation_views.enrollment_qr, name="moderator-invitation-qr"),
    path("admin/team/", invitation_views.team, name="team"),
    path("admin/creators/", creator_views.creators, name="creators"),
    path("admin/rights-holders/", rights_holder_views.rights_holders, name="rights-holders"),
    path("admin/creators/measures/", restriction_views.find, name="creator-measures-find"),
    path("admin/creators/measures/appeals/", restriction_views.appeals, name="creator-measure-appeals"),
    path("admin/creators/<uuid:target_id>/measures/", restriction_views.creator, name="creator-measures"),
    path("admin/business/", business_views.overview, name="business"),
    path("admin/business/categories/", business_views.categories, name="business-categories"),
    path("admin/business/access/", business_views.grants, name="business-grants"),
    path("admin/", views.dashboard, name="dashboard"),
    path("admin/moderation/previews/<uuid:preview_id>/", views.reviewer_preview, name="reviewer-preview"),
    path("admin/fraud/", views.fraud_holds, name="fraud"),
    path("admin/points/", views.points, name="points"),
    path("admin/audit/", views.audit, name="audit"),
    path("admin/account/", views.account, name="account"),
    path("admin/account/profile/", views.profile_edit, name="profile-edit"),
    path("admin/account/password/", views.password_change, name="password-change"),
    path("admin/account/sessions/", views.sessions, name="sessions"),
    path("admin/account/sessions/<uuid:session_id>/revoke/", views.revoke_session, name="revoke-session"),
    path("admin/logout/", views.logout, name="logout"),
]
for kind in ("videos", "reports", "appeals"):
    urlpatterns += [
        path(f"admin/moderation/{kind}/", views.moderation_queue, {"kind": kind}, name=f"moderation-{kind}"),
        path(f"admin/moderation/{kind}/<uuid:target_id>/", views.moderation_detail,
             {"kind": kind}, name=f"moderation-{kind}-detail"),
        path(f"admin/moderation/{kind}/<uuid:target_id>/assignments/", assignment_views.assign,
             {"kind": kind}, name=f"moderation-{kind}-assign"),
    ]
urlpatterns += [
    path("admin/moderation/edits/", edit_views.queue, name="moderation-edits"),
    path("admin/moderation/edits/<uuid:target_id>/", edit_views.detail, name="moderation-edits-detail"),
]
for kind in ("verifications", "profiles", "reports"):
    urlpatterns += [
        path(f"admin/business/{kind}/", business_views.queue, {"kind": kind}, name=f"business-{kind}"),
        path(f"admin/business/{kind}/<uuid:target_id>/", business_views.detail, {"kind": kind},
             name=f"business-{kind}-detail"),
    ]
