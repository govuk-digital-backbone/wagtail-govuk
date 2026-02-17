import os
from .base import *

DEBUG = True

SECRET_KEY = "abc123"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

WAGTAILADMIN_BASE_URL = "http://localhost:8000"
