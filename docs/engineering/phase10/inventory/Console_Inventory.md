# Administrator and moderator dashboard inventory (generated)

Source: `apps/web_django/web/urls.py`. 30 route declarations (some are generated in loops over a kind), 34 templates. Per-route authentication, MFA, role and CSRF behaviour is proven by `apps/web_django/tests/test_route_security_matrix.py` (`docs/engineering/phase5/P5-01_route_security_matrix.md`). There are **no** ordinary-user routes, and **no** pages for events, ticketing, advertising or financial review.

| Path | Route name | View |
| --- | --- | --- |
| /health/live |  | require_GET |
| /static/<path:asset> |  | views.static_asset |
| / |  | views.root |
| /moderator/ |  | RedirectView.as_view |
| /dashboard/ |  | RedirectView.as_view |
| /login/ |  | views.login |
| /login/mfa/ |  | views.login_mfa |
| /moderator-invitation/ |  | invitation_views.accept |
| /moderator-invitation/qr/ |  | invitation_views.enrollment_qr |
| /admin/team/ |  | invitation_views.team |
| /admin/creators/ |  | creator_views.creators |
| /admin/business/ |  | business_views.overview |
| /admin/business/categories/ |  | business_views.categories |
| /admin/business/access/ |  | business_views.grants |
| /admin/ |  | views.dashboard |
| /admin/moderation/previews/<uuid:preview_id>/ |  | views.reviewer_preview |
| /admin/fraud/ |  | views.fraud_holds |
| /admin/points/ |  | views.points |
| /admin/audit/ |  | views.audit |
| /admin/account/ |  | views.account |
| /admin/account/profile/ |  | views.profile_edit |
| /admin/account/password/ |  | views.password_change |
| /admin/account/sessions/ |  | views.sessions |
| /admin/account/sessions/<uuid:session_id>/revoke/ |  | views.revoke_session |
| /admin/logout/ |  | views.logout |
| /admin/moderation/{kind}/ |  | views.moderation_queue |
| /admin/moderation/{kind}/<uuid:target_id>/ |  | views.moderation_detail |
| /admin/moderation/{kind}/<uuid:target_id>/assignments/ |  | assignment_views.assign |
| /admin/business/{kind}/ |  | business_views.queue |
| /admin/business/{kind}/<uuid:target_id>/ |  | business_views.detail |

## Templates

account.html, account_form.html, admin_nav.html, audit.html, base.html, base_admin.html, business_categories.html, business_confirm.html, business_decision_form.html, business_grants.html, business_overview.html, business_profile.html, business_queue.html, business_report.html, business_result.html, business_tabs.html, business_verification.html, creator_confirm.html, creator_revoke_confirm.html, creators.html, dashboard.html, decision_confirm.html, decision_result.html, form.html, fraud.html, icon.html, moderation_detail.html, moderation_list.html, moderator_invitation.html, points_review.html, sessions.html, status.html, team.html, unavailable.html
