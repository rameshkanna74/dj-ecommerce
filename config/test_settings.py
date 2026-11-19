"""Settings used by the pytest suite (see [tool.pytest.ini_options] in pyproject.toml)."""

import os
import tempfile

os.environ["DJANGO_SKIP_DOTENV"] = "1"  # tests must not depend on a developer's local .env
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-used-anywhere-else")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost")
os.environ.setdefault("DJANGO_SECURE_SSL_REDIRECT", "False")
os.environ["DB_ENGINE"] = "sqlite"

from .settings import *  # noqa: E402,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
MEDIA_ROOT = tempfile.mkdtemp(prefix="corecart-test-media-")
STORAGES = {**STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "corecart-tests"}}
