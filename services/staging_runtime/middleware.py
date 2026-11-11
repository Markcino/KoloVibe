import logging
import re

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)
UUID = r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"
PUBLIC = re.compile(rf"/(?:videos|api/v1/videos(?:/{UUID})?|api/v1/creators/{UUID})")
CREATOR_ONBOARDING_PUBLIC = re.compile(
    rf"/api/v1/(?:creator-invitations|creator-applications(?:/{UUID}/decision)?|creators/me/(?:application|upload-eligibility))"
)
CREATOR_ONBOARDING_INTERNAL = re.compile(r"/internal/creators/onboarding/(?:invite|pending|review|status|submit|eligibility)")
ACCOUNTS = {
    "gateway": {"/api/v1/auth/" + name for name in
                ("register", "verify", "login", "refresh", "logout")} | {"/api/v1/me"},
    "identity": {"/internal/auth/" + name for name in
                 ("register", "verify", "login", "refresh", "validate", "revoke")},
}
INTERNAL = {
    "content": {"/internal/videos", "/internal/videos/detail", "/internal/videos/published-count"},
    "creators": {"/internal/creators/profile"},
    "audit": {"/internal/security-events"},
}


class RestrictedStagingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.is_secure():
            logger.warning("Rejected non-TLS staging request")
            return JsonResponse({"detail": "HTTPS required"}, status=403)
        # Validate Host even for views which never call request.get_host().
        request.get_host()
        path = request.path
        service = settings.KOLOVIBE_SERVICE_NAME
        if path in ("/health/live", "/health/ready", "/ops/verify"):
            return self.get_response(request)
        allowed = path == "/internal/probe" and request.method == "GET"
        allowed |= service == "gateway" and request.method == "GET" and bool(PUBLIC.fullmatch(path))
        allowed |= path in INTERNAL.get(service, set()) and request.method == "POST"
        allowed |= settings.STAGING_ACCOUNTS and path in ACCOUNTS.get(service, set())
        allowed |= getattr(settings, "STAGING_PRIVILEGED", False) and path in {
            "gateway": {"/api/v1/auth/mfa/verify"},
            "identity": {"/internal/auth/mfa/verify"},
        }.get(service, set())
        if getattr(settings, "STAGING_CREATOR_ONBOARDING", False):
            allowed |= service == "gateway" and bool(CREATOR_ONBOARDING_PUBLIC.fullmatch(path))
            allowed |= (service == "creators" and request.method == "POST"
                        and bool(CREATOR_ONBOARDING_INTERNAL.fullmatch(path)))
        if not allowed:
            logger.warning("Rejected gated staging route")
            return JsonResponse({"detail": "Not enabled in restricted staging"}, status=403)
        return self.get_response(request)
