from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Use a simpler static files storage in development (no manifest hashing)
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
