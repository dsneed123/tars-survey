import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-change-me-in-production-use-env-var")

DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "channels",
    "accounts",
    "pages",
    "inquiries",
    "members",
    "projects",
    "tasks",
    "workers",
    "analytics",
]

AUTH_USER_MODEL = "accounts.CustomUser"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"

SITE_URL = "https://usetars.dev"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "analytics.middleware.PageViewMiddleware",
]

ROOT_URLCONF = "tars_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "pages.context_processors.site_url",
            ],
        },
    },
]

WSGI_APPLICATION = "tars_site.wsgi.application"
ASGI_APPLICATION = "tars_site.asgi.application"

_default_db = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", _default_db),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Media files (user uploads / task attachments)
# ---------------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# In production, use S3-compatible storage when AWS credentials are provided.
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
if not DEBUG and AWS_STORAGE_BUCKET_NAME:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
    AWS_DEFAULT_ACL = "private"
    AWS_S3_FILE_OVERWRITE = False
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN or f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'}/"

CSRF_TRUSTED_ORIGINS = [
    "https://usetars.dev",
    "https://www.usetars.dev",
    "https://tars-survey-production.up.railway.app",
]

# Allow Railway to pass the real scheme through the proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cookie settings for HTTPS behind proxy
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# Email configuration
# In development (DEBUG=True), emails print to the terminal console.
# In production, set EMAIL_BACKEND to smtp and provide SMTP env vars.
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.mailgun.org")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "TARS <noreply@tarsai.dev>")
TARS_ADMIN_EMAIL = os.environ.get("TARS_ADMIN_EMAIL", "admin@tarsai.dev")

# TARS Controller API — local Mac Mini brain
TARS_CONTROLLER_URL = os.environ.get("TARS_CONTROLLER_URL", "")
TARS_API_KEY = os.environ.get("TARS_API_KEY", "")

# GitHub personal access token used for API calls (commits, branches, PRs, diffs)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ---------------------------------------------------------------------------
# Django Channels — WebSocket support
# ---------------------------------------------------------------------------
# In production set REDIS_URL to a Redis instance.
# Falls back to in-memory channel layer for local development (single-process only).
_REDIS_URL = os.environ.get("REDIS_URL", "")
if _REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [_REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
