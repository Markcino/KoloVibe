"""Local-only Django template client. Deployment settings require separate review."""

import os
from pathlib import Path
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("KOLOVIBE_ENV") != "local":
    raise RuntimeError("Web deployment is not authorized")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 32:
    raise RuntimeError("A private web DJANGO_SECRET_KEY is required")
GATEWAY_URL = os.environ.get("KOLOVIBE_GATEWAY_URL", "")
origin = urlsplit(GATEWAY_URL)
if origin.scheme != "http" or origin.hostname != "127.0.0.1" or origin.path not in ("", "/"):
    raise RuntimeError("Local web must use a loopback gateway URL")
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
ROOT_URLCONF = "web.urls"
INSTALLED_APPS = ["django.contrib.staticfiles"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = False  # This settings module runs on loopback HTTP only.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
USE_TZ = True
