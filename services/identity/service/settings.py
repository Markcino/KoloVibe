"""Service settings. Development defaults are forbidden outside an explicit local environment."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENVIRONMENT = os.environ.get("KOLOVIBE_ENV")
if ENVIRONMENT != "local":
    raise RuntimeError(
        "Production/staging service settings are not configured. "
        "This application may currently run only with KOLOVIBE_ENV=local."
    )
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("DJANGO_SECRET_KEY must be set to a unique local secret of at least 32 characters")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
ROOT_URLCONF = "service.urls"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "service"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
TEMPLATES = []
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "local.sqlite3"}
}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "service.Account"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
