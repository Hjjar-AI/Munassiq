"""Environment-driven Django backend settings."""
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
TRUST_LOCAL_PROXY = boolean("DJANGO_TRUST_PROXY")
if TRUST_LOCAL_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

runtime = Path(os.environ.get("APP_RUNTIME_DIR", "runtime")).expanduser()
RUNTIME_ROOT = runtime if runtime.is_absolute() else PROJECT_ROOT / runtime
MEDIA_ROOT = RUNTIME_ROOT / "media"
PRIVATE_CREDENTIAL_ROOT = RUNTIME_ROOT / "private_credentials"
STATIC_ROOT = RUNTIME_ROOT / "static"
# Directories are prepared by an explicit script, not by importing settings.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
    "NAME": RUNTIME_ROOT / "database.sqlite3", "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"}}}
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.staticfiles",
    "rest_framework", "drf_spectacular", "core", "accounts"]
AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
MIDDLEWARE = ["core.middleware.ClientAddressMiddleware", "django.middleware.security.SecurityMiddleware",
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
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.SessionAuthentication"], "UNAUTHENTICATED_USER": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]}
SPECTACULAR_SETTINGS = {"TITLE": "مُنسِّق API", "DESCRIPTION": "Professional directory and events",
    "SERVE_INCLUDE_SCHEMA": False}
LOG_FILE_NAME = os.environ.get("APP_LOG_NAME", "server")
if not LOG_FILE_NAME.replace("-", "").replace("_", "").isalnum():
    raise ImproperlyConfigured("APP_LOG_NAME must contain only letters, digits, hyphens or underscores")
LOGGING = {"version": 1, "disable_existing_loggers": False,
    "formatters": {"daily": {"format": "{asctime} {levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "daily"},
        "file": {"class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(RUNTIME_ROOT / "logs" / (LOG_FILE_NAME + ".log")),
            "when": "midnight", "utc": True, "backupCount": 30, "formatter": "daily"}},
    "root": {"handlers": ["console", "file"], "level": "INFO"}}

# Authentication defaults are configurable, not hardcoded secrets.
from .environment import positive_integer
PASSWORD_MIN_LENGTH = positive_integer("PASSWORD_MIN_LENGTH", 6)
if PASSWORD_MIN_LENGTH < 6:
    raise ImproperlyConfigured("PASSWORD_MIN_LENGTH must be at least 6")
SESSION_DAYS = positive_integer("SESSION_DAYS", 30)
ACCESS_TOKEN_MINUTES = positive_integer("ACCESS_TOKEN_MINUTES", 15)
LOGIN_LIMIT = positive_integer("LOGIN_LIMIT", 10)
STAFF_LOGIN_LIMIT = positive_integer("STAFF_LOGIN_LIMIT", 5)
LOGIN_WINDOW_MINUTES = positive_integer("LOGIN_WINDOW_MINUTES", 15)
LOGIN_LOCKOUT_MINUTES = positive_integer("LOGIN_LOCKOUT_MINUTES", 15)
ADMIN_IP_RESTRICTION = boolean("ADMIN_IP_RESTRICTION")
ADMIN_ALLOWED_NETWORKS = csv("ADMIN_ALLOWED_NETWORKS")
if ADMIN_IP_RESTRICTION and not ADMIN_ALLOWED_NETWORKS:
    raise ImproperlyConfigured("Admin IP restriction requires an allowlist")
from ipaddress import ip_network
for network in ADMIN_ALLOWED_NETWORKS:
    try:
        ip_network(network)
    except ValueError as exc:
        raise ImproperlyConfigured("Invalid admin IP network") from exc
from urllib.parse import urlsplit
APP_PUBLIC_URL = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
public_url = urlsplit(APP_PUBLIC_URL)
if public_url.scheme not in {"http", "https"} or not public_url.hostname or public_url.query or public_url.fragment or public_url.username or public_url.path:
    raise ImproperlyConfigured("APP_PUBLIC_URL must be a complete origin without path or credentials")
if not DEBUG and public_url.scheme != "https":
    raise ImproperlyConfigured("Production APP_PUBLIC_URL requires HTTPS")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = positive_integer("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = boolean("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.environ.get("EMAIL_FROM", "")
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

FILE_UPLOAD_HANDLERS = ["accounts.uploads.SizeLimitHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler"]
