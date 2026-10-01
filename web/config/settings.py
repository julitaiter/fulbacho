import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", os.getenv("SECRET_KEY", "dev-only-secret-key"))
DEBUG = os.getenv("DJANGO_DEBUG", os.getenv("DEBUG", "True")).lower() == "true"
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8001/api/v1").rstrip("/")
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "10"))

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "" if PRODUCTION else "127.0.0.1,localhost").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "fulbacho",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "fulbacho.auth.ApiAuthMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

web_database_url = os.getenv("WEB_DATABASE_URL")
if web_database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            web_database_url,
            conn_max_age=600,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "web.sqlite3",
        }
    }

if PRODUCTION:
    if not os.getenv("DJANGO_SECRET_KEY") or os.getenv("DJANGO_DEBUG", "").lower() != "false" or DEBUG:
        raise ImproperlyConfigured("Production requires DJANGO_SECRET_KEY and DJANGO_DEBUG=false.")
    if SECRET_KEY == os.getenv("API_SECRET_KEY"):
        raise ImproperlyConfigured("Application secrets must be distinct.")
    if not ALLOWED_HOSTS or any("*" in host or host.startswith(".") for host in ALLOWED_HOSTS):
        raise ImproperlyConfigured("Set ALLOWED_HOSTS to explicit production hostnames.")
    if not CSRF_TRUSTED_ORIGINS or any(
        not origin.startswith("https://") or "*" in origin for origin in CSRF_TRUSTED_ORIGINS
    ):
        raise ImproperlyConfigured("Set CSRF_TRUSTED_ORIGINS to explicit HTTPS origins.")
    if not web_database_url or DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("Production requires a PostgreSQL WEB_DATABASE_URL.")
    domain_url = os.getenv("DATABASE_URL", "")
    if not domain_url or unquote(urlsplit(domain_url).path) == unquote(urlsplit(web_database_url).path):
        raise ImproperlyConfigured("DATABASE_URL and WEB_DATABASE_URL must name separate databases.")
    if API_BASE_URL != "http://127.0.0.1:8001/api/v1":
        raise ImproperlyConfigured("Production API_BASE_URL must be http://127.0.0.1:8001/api/v1.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if PRODUCTION else None

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
LOGIN_URL = "login"
