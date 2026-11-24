"""Business owner and administration routes, each behind its own capability flag (closed by default)."""
from django.urls import path

from ..capabilities import enabled


def patterns():
    routes = []
    if enabled("business_owner"):
        from ..business import business_endpoint

        def route(url, **operations):
            return path("api/v1/" + url, business_endpoint, {"operations": operations})

        routes += [
            route("me/businesses", GET="list_mine", POST="register"),
            route("me/businesses/<uuid:business_id>", GET="get_mine"),
            route("me/businesses/<uuid:business_id>/members", GET="member_list"),
            route("me/businesses/<uuid:business_id>/members/invitations", POST="staff_invite"),
            route("me/businesses/<uuid:business_id>/members/invitations/<uuid:invitation_id>", DELETE="staff_invitation_revoke"),
            route("me/businesses/<uuid:business_id>/members/<uuid:member_id>", DELETE="member_remove"),
            route("me/businesses/<uuid:business_id>/leave", POST="member_leave"),
            route("me/business-invitations/redeem", POST="staff_redeem"),
            route("me/businesses/<uuid:business_id>/verification", GET="verification_status", POST="verification_submit"),
            route("me/businesses/<uuid:business_id>/verification/evidence", POST="verification_respond"),
            route("me/businesses/<uuid:business_id>/profile", GET="profile_get", PATCH="profile_edit"),
            route("me/businesses/<uuid:business_id>/profile/submit", POST="profile_submit"),
            route("me/businesses/<uuid:business_id>/hours", PUT="hours_replace"),
            route("business-categories", GET="category_list"),
        ]
    if enabled("business_review_admin"):
        from ..business import business_endpoint

        def route(url, **operations):
            return path("api/v1/" + url, business_endpoint, {"operations": operations})

        routes += [
            route("admin/business-registration-grants/<uuid:account_id>", PUT="registration_grant"),
            route("admin/business-reviewer-grants", PUT="reviewer_grant"),
            route("admin/business-categories/<slug:slug>", PUT="category_put"),
            route("moderation/business-profile-revisions", GET="profile_queue"),
            route("moderation/business-profile-revisions/<uuid:revision_id>", GET="profile_revision"),
            route("moderation/business-profile-revisions/<uuid:revision_id>/decision", POST="profile_decide"),
            route("moderation/business-verifications", GET="verification_queue"),
            route("moderation/business-verifications/<uuid:case_id>", GET="verification_case"),
            route("moderation/business-verifications/<uuid:case_id>/claim", POST="verification_claim"),
            route("moderation/business-verifications/<uuid:case_id>/decision", POST="verification_decide"),
        ]
    return routes
