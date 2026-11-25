"""Fail-closed application settings; production activation requires approved deployment configuration."""
import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
ENVIRONMENT = os.environ.get("KOLOVIBE_ENV")
if ENVIRONMENT not in ("local", "staging"):
    raise RuntimeError("Production settings are not authorized; explicit local or staging profile required.")
if ENVIRONMENT == "staging":
    from staging_runtime import secret
    SECRET_KEY = secret("DJANGO_SECRET_KEY_FILE")
else:
    SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("A unique DJANGO_SECRET_KEY of at least 32 characters is required")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
ROOT_URLCONF = "service.urls"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "service"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "service.service_auth.ServiceAuthMiddleware",
]
TEMPLATES = []
_pg_vars = ("KOLOVIBE_DB_NAME", "KOLOVIBE_DB_USER", "KOLOVIBE_DB_HOST",
            "KOLOVIBE_DB_PASSWORD_FILE", "KOLOVIBE_DB_SSLROOTCERT")
if any(os.getenv(k) for k in _pg_vars):
    if not all(os.getenv(k) for k in _pg_vars):
        raise RuntimeError("Incomplete PostgreSQL database configuration")
    _password = Path(os.environ["KOLOVIBE_DB_PASSWORD_FILE"]).read_text().strip()
    if not _password:
        raise RuntimeError("Empty PostgreSQL database credential")
    from staging_runtime import database_options
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["KOLOVIBE_DB_NAME"],
        "USER": os.environ["KOLOVIBE_DB_USER"],
        "PASSWORD": _password,
        "HOST": os.environ["KOLOVIBE_DB_HOST"],
        "PORT": os.getenv("KOLOVIBE_DB_PORT", "5432"),
        "OPTIONS": {
            "sslmode": "verify-full",
            "sslrootcert": os.environ["KOLOVIBE_DB_SSLROOTCERT"],
            "options": database_options("identity"),
        },
        "CONN_MAX_AGE": 0,
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "local.sqlite3",
    }}
KOLOVIBE_SERVICE_NAME = "identity"
# ADR-013 amendment A-1: long emailed tokens issued before migration 0010 stay valid only until they
# expire (24 h at most). Set to "0" once that window has passed; the branch is then deleted.
KOLOVIBE_ACCEPT_LEGACY_LONG_CODES = os.environ.get("KOLOVIBE_ACCEPT_LEGACY_LONG_CODES", "1") == "1"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "service.Account"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
EMAIL_HOST = os.environ.get("KOLOVIBE_SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("KOLOVIBE_SMTP_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("KOLOVIBE_SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("KOLOVIBE_SMTP_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("KOLOVIBE_FROM_EMAIL", "")
if ENVIRONMENT == "staging":
    from staging_runtime import configure
    configure(globals())
