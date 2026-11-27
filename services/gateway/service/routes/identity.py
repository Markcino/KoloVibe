"""Account, session, settings, and privacy routes."""
from django.urls import path


def patterns():
    from .. import accounts
    from ..compatibility import compatibility
    from ..preferences_privacy import preferences, privacy_export, privacy_requests
    from .. import account_lookup, legal, moderator_invitations, privacy_review

    return [
        path("api/v1/admin/moderator-invitations", moderator_invitations.collection),
        path("api/v1/admin/accounts/lookup", account_lookup.lookup),
        # Decision C: privacy request review and account holds (Identity authorises the administrator).
        path("api/v1/admin/privacy-requests", privacy_review.collection),
        *[path(f"api/v1/admin/privacy-requests/<uuid:target_id>/{operation}", privacy_review.step,
               {"operation": operation}) for operation in privacy_review.STEPS],
        path("api/v1/admin/accounts/<uuid:target_id>/holds", privacy_review.holds),
        path("api/v1/admin/account-holds/<uuid:target_id>/release", privacy_review.release),
        path("api/v1/admin/moderator-invitations/<uuid:invitation_id>/revoke", moderator_invitations.revoke),
        path("api/v1/auth/moderator-invitations/setup", moderator_invitations.accept),
        path("api/v1/auth/moderator-invitations/complete", moderator_invitations.accept, {"complete": True}),
        path("api/v1/app/compatibility", compatibility, name="app-compatibility"),
        *[path(f"api/v1/legal/{kind}", legal.document, {"kind": kind}, name=f"legal-{kind}") for kind in legal.KINDS],
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
        path("api/v1/me/reauthenticate", accounts.reauthenticate, name="reauthenticate"),
        path("api/v1/me/step-up", accounts.step_up, name="step-up"),
        path("api/v1/me/legal", legal.acceptance, name="account-legal"),
        path("api/v1/me/marketing-consent", legal.marketing_consent, name="account-marketing-consent"),
        path("api/v1/me/preferences", preferences, name="account-preferences"),
        path("api/v1/me/privacy-requests", privacy_requests, name="account-privacy-requests"),
        path("api/v1/me/privacy-requests/<uuid:target_id>/export", privacy_export, name="account-privacy-export"),
        path("api/v1/me/sessions/<uuid:session_id>", accounts.revoke_session, name="revoke-account-session"),
        path("api/v1/me", accounts.me, name="me"),
    ]
