import logging
import re

from django.conf import settings
from django.http import JsonResponse

from . import capabilities

logger = logging.getLogger(__name__)
UUID = r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"
PUBLIC = re.compile(rf"/(?:videos|api/v1/videos(?:/{UUID})?|api/v1/creators/(?:{UUID}|search))")
CREATOR_ONBOARDING_PUBLIC = re.compile(
    rf"/api/v1/(?:creator-invitations(?:/{UUID}/revoke)?|creator-applications(?:/{UUID}/decision)?|creators/me/(?:application|upload-eligibility))"
)
CREATOR_ONBOARDING_INTERNAL = re.compile(r"/internal/creators/onboarding/(?:invite|pending|outstanding|revoke|review|status|submit|eligibility)")
ACCOUNTS = {
    # Decision B: registration needs the current legal texts, and a signed-in person must be able to re-accept them.
    "gateway": {"/api/v1/auth/" + name for name in
                ("register", "verify", "login", "refresh", "logout")} | {"/api/v1/me"}
               | {"/api/v1/legal/" + kind for kind in ("terms", "privacy", "marketing")}
               | {"/api/v1/me/legal", "/api/v1/me/marketing-consent"},
    "identity": {"/internal/auth/" + name for name in
                 ("register", "verify", "login", "refresh", "validate", "revoke", "legal", "legal/document")},
}
INTERNAL = {
    "content": {"/internal/videos", "/internal/videos/detail", "/internal/videos/published-count"},
    "creators": {"/internal/creators/profile", "/internal/creators/search"},
    "audit": {"/internal/security-events"},
}


def route_allowed(service, method, path, *, accounts=False, privileged=False, onboarding=False,
                  capability_set=frozenset()):
    """The whole staging allow-list as one pure function (the middleware and the tests share it)."""
    if path in ("/health/live", "/health/ready", "/ops/verify"):
        return True
    allowed = path == "/internal/probe" and method == "GET"
    allowed |= service == "gateway" and method == "GET" and bool(PUBLIC.fullmatch(path))
    allowed |= path in INTERNAL.get(service, set()) and method == "POST"
    allowed |= accounts and path in ACCOUNTS.get(service, set())
    # Gateway owns the onboarding switch and attests eligibility over signed peers.
    # Identity owns this account mutation; it needs no new caller or peer credential.
    allowed |= accounts and service == "identity" and method == "POST" and path == "/internal/auth/creator-role"
    # R1 capabilities: explicit (service, capability, method, path) rules; closed unless named.
    allowed |= capabilities.allowed(service, capability_set, method, path, privileged=privileged)
    allowed |= privileged and path in {
        "gateway": {"/api/v1/auth/mfa/verify"},
        "identity": {"/internal/auth/mfa/verify"},
    }.get(service, set())
    if onboarding:
        allowed |= service == "gateway" and bool(CREATOR_ONBOARDING_PUBLIC.fullmatch(path))
        allowed |= service == "creators" and method == "POST" and bool(CREATOR_ONBOARDING_INTERNAL.fullmatch(path))
    return allowed


class RestrictedStagingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.is_secure():
            logger.warning("Rejected non-TLS staging request")
            return JsonResponse({"detail": "HTTPS required"}, status=403)
        # Validate Host even for views which never call request.get_host().
        request.get_host()
        if not route_allowed(
                settings.KOLOVIBE_SERVICE_NAME, request.method, request.path, accounts=settings.STAGING_ACCOUNTS,
                privileged=getattr(settings, "STAGING_PRIVILEGED", False),
                onboarding=getattr(settings, "STAGING_CREATOR_ONBOARDING", False),
                capability_set=getattr(settings, "STAGING_CAPABILITIES", frozenset())):
            logger.warning("Rejected gated staging route")
            return JsonResponse({"detail": "Not enabled in restricted staging"}, status=403)
        return self.get_response(request)
