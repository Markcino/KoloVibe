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
        ]
    if enabled("business_review_admin"):
        from ..business import business_endpoint

        routes.append(path("api/v1/admin/business-registration-grants/<uuid:account_id>", business_endpoint,
                           {"operations": {"PUT": "registration_grant"}}))
    return routes
