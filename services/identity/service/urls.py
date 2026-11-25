from django.urls import path
from django.http import JsonResponse
from .health import liveness
from . import accounts
from .mfa import verify_mfa
from . import account_lookup, legal, moderator_invitations, step_up
from .preferences_privacy import preferences, privacy_requests

urlpatterns = [
    path("internal/auth/moderator-invitations", moderator_invitations.administer),
    path("internal/auth/account-lookup", account_lookup.lookup),
    path("internal/auth/moderator-invitations/setup", moderator_invitations.accept),
    path("internal/auth/moderator-invitations/complete", moderator_invitations.accept, {"complete": True}),
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
    path("internal/auth/register", accounts.register, name="internal-register"),
    path("internal/auth/verification/resend", accounts.resend_verification, name="verification-resend"),
    path("internal/auth/verify", accounts.verify_email, name="internal-verify"),
    path("internal/auth/password/reset-request", accounts.request_password_reset, name="internal-reset-request"),
    path("internal/auth/password/reset", accounts.reset_password, name="internal-reset-password"),
    path("internal/auth/password/change", accounts.change_password, name="internal-change-password"),
    path("internal/auth/profile", accounts.update_profile, name="internal-update-profile"),
    path("internal/auth/reauthenticate", accounts.reauthenticate, name="internal-reauthenticate"),
    path("internal/auth/legal/document", legal.document, name="internal-legal-document"),
    path("internal/auth/legal", legal.manage, name="internal-legal"),
    path("internal/auth/step-up", step_up.issue, name="internal-step-up"),
    path("internal/auth/step-up/consume", step_up.consume, name="internal-step-up-consume"),
    path("internal/auth/preferences", preferences, name="internal-preferences"),
    path("internal/auth/privacy-requests", privacy_requests, name="internal-privacy-requests"),
    path("internal/auth/login", accounts.login, name="internal-login"),
    path("internal/auth/mfa/verify", verify_mfa, name="internal-mfa-verify"),
    path("internal/auth/refresh", accounts.refresh, name="internal-refresh"),
    path("internal/auth/standing", accounts.standing_context, name="internal-standing"),
    path("internal/auth/creator-role", accounts.sync_creator_role, name="internal-creator-role"),
    path("internal/auth/validate", accounts.validate_access, name="internal-validate"),
    path("internal/auth/sessions", accounts.manage_sessions, name="internal-sessions"),
    path("internal/auth/revoke", accounts.revoke, name="internal-revoke"),
]
