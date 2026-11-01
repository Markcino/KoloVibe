from django.urls import path
from django.http import JsonResponse
from .health import liveness
from . import accounts

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
    path("internal/auth/register", accounts.register, name="internal-register"),
    path("internal/auth/verify", accounts.verify_email, name="internal-verify"),
    path("internal/auth/login", accounts.login, name="internal-login"),
    path("internal/auth/refresh", accounts.refresh, name="internal-refresh"),
    path("internal/auth/validate", accounts.validate_access, name="internal-validate"),
    path("internal/auth/revoke", accounts.revoke, name="internal-revoke"),
]
