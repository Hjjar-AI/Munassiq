"""Core settings. No account model or database schema is created yet."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
from .environment import boolean, csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a random value of at least 50 characters")
DEBUG = boolean("DJANGO_DEBUG")
ALLOWED_HOSTS = csv("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list explicit hosts")
CSRF_TRUSTED_ORIGINS = csv("DJANGO_CSRF_TRUSTED_ORIGINS")
SECURE_SSL_REDIRECT = boolean("DJANGO_HTTPS_ONLY", True)
if not DEBUG and not SECURE_SSL_REDIRECT:
    raise ImproperlyConfigured("Production requires DJANGO_HTTPS_ONLY=true")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if boolean("DJANGO_TRUST_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

runtime = Path(os.environ.get("APP_RUNTIME_DIR", "runtime")).expanduser()
RUNTIME_ROOT = runtime if runtime.is_absolute() else PROJECT_ROOT / runtime
MEDIA_ROOT = RUNTIME_ROOT / "media"
PRIVATE_CREDENTIAL_ROOT = RUNTIME_ROOT / "private_credentials"
STATIC_ROOT = RUNTIME_ROOT / "static"
# Directories are prepared by an explicit script, not by importing settings.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
    "NAME": RUNTIME_ROOT / "database.sqlite3", "OPTIONS": {"timeout": 20}}}
INSTALLED_APPS = ["django.contrib.staticfiles", "rest_framework", "drf_spectacular", "core"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware",
    "django.middleware.locale.LocaleMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": [
        "django.template.context_processors.request"]}}]
LANGUAGE_CODE = "ar"
LANGUAGES = [("ar", "العربية"), ("en", "English")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [], "UNAUTHENTICATED_USER": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]}
SPECTACULAR_SETTINGS = {"TITLE": "مُنسِّق API", "DESCRIPTION": "Professional directory and events",
    "SERVE_INCLUDE_SCHEMA": False}
LOGGING = {"version": 1, "disable_existing_loggers": False,
    "formatters": {"daily": {"format": "{asctime} {levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "daily"},
        "file": {"class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(RUNTIME_ROOT / "logs" / "server.log"),
            "when": "midnight", "utc": True, "backupCount": 30, "formatter": "daily"}},
    "root": {"handlers": ["console", "file"], "level": "INFO"}}
