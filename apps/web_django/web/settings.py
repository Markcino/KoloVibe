"""Django template client for local work and the restricted AWS web host."""

import base64
import hashlib
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.fernet import Fernet

BASE_DIR = Path(__file__).resolve().parent.parent
ENVIRONMENT = os.environ.get("KOLOVIBE_ENV")
if ENVIRONMENT not in ("local", "staging"):
    raise RuntimeError("Unsupported web environment")

if ENVIRONMENT == "staging":
    secret_path = os.environ.get("KOLOVIBE_WEB_SECRET_KEY_FILE", "")
    if secret_path != "/run/secrets/web_django_key":
        raise RuntimeError("Staging web requires its fixed secret mount")
    def private_file(path):
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o400):
                raise RuntimeError("Staging web secret must be owner-only")
            value = os.read(descriptor, 257).decode("utf-8").strip()
            if not value or len(value) > 256:
                raise RuntimeError("Invalid staging web secret")
            return value
        finally:
            os.close(descriptor)

    SECRET_KEY = private_file(secret_path)
    if os.environ.get("KOLOVIBE_WEB_TOKEN_KEY_FILE") != "/run/secrets/web_token_key":
        raise RuntimeError("Staging web requires a separate credential-encryption key")
    WEB_TOKEN_KEY = private_file("/run/secrets/web_token_key").encode("ascii")
    Fernet(WEB_TOKEN_KEY)
    if os.environ.get("KOLOVIBE_WEB_DB_PASSWORD_FILE") != "/run/secrets/web_db_password":
        raise RuntimeError("Staging web requires its own database role")
    WEB_DB_PASSWORD = private_file("/run/secrets/web_db_password")
    if os.environ.get("KOLOVIBE_WEB_DB_CA_FILE") != "/run/secrets/web_db_ca":
        raise RuntimeError("Staging web requires verified database TLS")
    if os.environ.get("KOLOVIBE_WEB_GATEWAY_CA_FILE") != "/run/secrets/web_gateway_ca":
        raise RuntimeError("Staging web requires verified gateway TLS")
    GATEWAY_CA = "/run/secrets/web_gateway_ca"
else:
    SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
    # Local fixture only; staging retains its independently provisioned key.
    WEB_TOKEN_KEY = base64.urlsafe_b64encode(hashlib.sha256(
        ("kolovibe-local-web-credentials:" + SECRET_KEY).encode()).digest())
if len(SECRET_KEY) < 32:
    raise RuntimeError("A private web DJANGO_SECRET_KEY is required")
GATEWAY_URL = os.environ.get("KOLOVIBE_GATEWAY_URL", "")
origin = urlsplit(GATEWAY_URL)
if (origin.path not in ("", "/") or origin.username is not None
        or origin.password is not None or origin.query or origin.fragment
        or (ENVIRONMENT == "staging" and GATEWAY_URL != "https://gateway:8000")
        or (ENVIRONMENT == "local" and (origin.scheme != "http" or origin.hostname != "127.0.0.1"))):
    raise RuntimeError("Web gateway origin is not approved")
GATEWAY_HOST = None
DEBUG = False
ALLOWED_HOSTS = (["kolovibe.cabetechs.shop"] if ENVIRONMENT == "staging"
                 else ["127.0.0.1", "localhost", "testserver"])
ROOT_URLCONF = "web.urls"
INSTALLED_APPS = ["django.contrib.staticfiles", "django.contrib.sessions", "web"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "web.security.AdminSecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
CSRF_COOKIE_SECURE = ENVIRONMENT == "staging"
SESSION_COOKIE_SECURE = ENVIRONMENT == "staging"
SESSION_COOKIE_NAME = "__Host-kolovibe_session" if ENVIRONMENT == "staging" else "sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 15 * 60
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_PATH = "/"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
CSRF_TRUSTED_ORIGINS = ["https://kolovibe.cabetechs.shop"] if ENVIRONMENT == "staging" else []
SECURE_PROXY_SSL_HEADER = (("HTTP_X_FORWARDED_PROTO", "https") if ENVIRONMENT == "staging" else None)
SECURE_SSL_REDIRECT = ENVIRONMENT == "staging"
# Thirty days for the single approved host. Subdomains of the shared apex are not covered
# and preload is not requested until every subdomain is confirmed HTTPS-only.
SECURE_HSTS_SECONDS = 30 * 86400 if ENVIRONMENT == "staging" else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
USE_TZ = True
if ENVIRONMENT == "staging":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "kolovibe_staging", "USER": "kolovibe_web_app",
        "PASSWORD": WEB_DB_PASSWORD, "HOST": "kolovibe-postgres", "PORT": "5432",
        "OPTIONS": {"sslmode": "verify-full", "sslrootcert": "/run/secrets/web_db_ca",
                    "options": "-c search_path=web"},
        "CONN_MAX_AGE": 0,
    }}
else:
    # Local test fixture only. Staging images remove SQLite and cannot select this profile.
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "web-local.sqlite3"}}

CSRF_FAILURE_VIEW = "web.views.error_403"
