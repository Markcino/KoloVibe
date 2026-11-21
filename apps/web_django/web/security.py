"""Browser protections for the server-rendered privileged console."""
from django.utils.cache import patch_cache_control


class AdminSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'none'; style-src 'self'; img-src 'self'; "
            "media-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.setdefault("Referrer-Policy", "same-origin")
        response["Cross-Origin-Opener-Policy"] = "same-origin"
        if not request.path.startswith("/static/") and request.path != "/health/live":
            patch_cache_control(response, private=True, no_store=True, no_cache=True, must_revalidate=True, max_age=0)
            response["Pragma"] = "no-cache"
        return response
