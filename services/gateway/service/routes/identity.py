"""Account, session, settings, and privacy routes."""
from django.urls import path


def patterns():
    from .. import accounts
    from ..preferences_privacy import preferences, privacy_requests

    return [
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
    ]
