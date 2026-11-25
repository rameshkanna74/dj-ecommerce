"""
CoreCart settings.

All deployment-specific values come from environment variables. A local
``.env`` file (see ``.env.example``) is read automatically for convenience;
real environment variables always take precedence over it.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Minimal KEY=VALUE loader so local development needs no extra package."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if not os.environ.get("DJANGO_SKIP_DOTENV"):
    _load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        # Development-only fallback. Never used when DEBUG is off.
        SECRET_KEY = "django-insecure-local-development-only"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

BASE_URL = env("CORECART_BASE_URL", "http://localhost:8000").rstrip("/")
CORECART_VERSION = "1.0.0"

# URL prefix of the Django admin (change it in production to reduce automated probing).
ADMIN_URL = env("DJANGO_ADMIN_URL", "admin/").strip("/") + "/"

AUTH_USER_MODEL = "accounts.CustomUser"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.forms",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "core",
    "accounts",
    "products",
    "cart",
    "orders",
    "analytics",
    "support",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",  # ETag / 304 Not Modified
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "core.context_processors.marketplace",
            ],
        },
    },
]

FORM_RENDERER = "core.forms.CoreFormRenderer"

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------
# Database: SQLite by default, PostgreSQL when DB_ENGINE=postgresql
# --------------------------------------------------------------------------
DB_ENGINE = env("DB_ENGINE", "sqlite").lower()
if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "corecart"),
            "USER": env("DB_USER", ""),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "ATOMIC_REQUESTS": False,
        }
    }
elif DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
            "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
        }
    }
else:
    raise ImproperlyConfigured(f"Unsupported DB_ENGINE '{DB_ENGINE}'. Use 'sqlite' or 'postgresql'.")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = ["accounts.backends.UsernameOrEmailBackend"]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "core:home"

# --------------------------------------------------------------------------
# Sessions & security
# --------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(env("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
    if env_bool("DJANGO_BEHIND_PROXY", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static & media
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(env("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))

MEDIA_URL = env("DJANGO_MEDIA_URL", "/media/")
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

# Uploaded media: local disk (default) or any S3-compatible bucket (AWS S3, Cloudflare R2,
# MinIO, ...). S3 credentials come from the standard AWS_ACCESS_KEY_ID /
# AWS_SECRET_ACCESS_KEY environment variables. Requires the `production` extra.
MEDIA_STORAGE = env("MEDIA_STORAGE", "local").lower()
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Hashed filenames in production so static assets can be cached forever.
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    },
}
if MEDIA_STORAGE == "s3":
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("S3_BUCKET_NAME", ""),
            "region_name": env("S3_REGION", "") or None,
            "endpoint_url": env("S3_ENDPOINT_URL", "") or None,
            "custom_domain": env("S3_CUSTOM_DOMAIN", "") or None,  # e.g. a CDN in front of the bucket
            "location": env("S3_MEDIA_PREFIX", "media"),
            "file_overwrite": False,
            "querystring_auth": env_bool("S3_SIGNED_URLS", False),
        },
    }
    if not STORAGES["default"]["OPTIONS"]["bucket_name"]:
        raise ImproperlyConfigured("S3_BUCKET_NAME is required when MEDIA_STORAGE=s3.")
elif MEDIA_STORAGE != "local":
    raise ImproperlyConfigured("MEDIA_STORAGE must be 'local' or 's3'.")

# Upload limits (bytes)
CORECART_MAX_IMAGE_SIZE = int(env("CORECART_MAX_IMAGE_SIZE", str(2 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
FILE_UPLOAD_PERMISSIONS = 0o644

# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------
# Use Redis in production: API rate limits and cached navigation data must be shared
# by every worker process. Requires the `production` extra.
REDIS_URL = env("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": env("CACHE_KEY_PREFIX", "corecart"),
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "corecart",
        }
    }

# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
# Django 6.1+ mailer configuration. Environment variable names stay familiar.
_EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
_EMAIL_OPTIONS = {}
if _EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    _EMAIL_OPTIONS = {
        "host": env("EMAIL_HOST", "localhost"),
        "port": int(env("EMAIL_PORT", "25")),
        "username": env("EMAIL_HOST_USER", ""),
        "password": env("EMAIL_HOST_PASSWORD", ""),
        "use_tls": env_bool("EMAIL_USE_TLS", False),
        "use_ssl": env_bool("EMAIL_USE_SSL", False),
        "timeout": int(env("EMAIL_TIMEOUT", "10")),
    }
MAILERS = {"default": {"BACKEND": _EMAIL_BACKEND, "OPTIONS": _EMAIL_OPTIONS}}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "CoreCart <noreply@corecart.local>")
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# --------------------------------------------------------------------------
# Marketplace configuration
# --------------------------------------------------------------------------
# Payment methods offered at checkout. Both are "offline" methods: an order is
# never marked as paid until an administrator confirms the payment.
CORECART_PAYMENT_METHODS = env_list("CORECART_PAYMENT_METHODS", "cod,bank_transfer")
CORECART_CURRENCY_SYMBOL = env("CORECART_CURRENCY_SYMBOL", "$")
CORECART_RECENTLY_VIEWED_LIMIT = 8

# Public URL of a separate frontend, if any. Used for links in API-triggered emails
# (e.g. password reset). Empty means links point at this Django site.
CORECART_FRONTEND_URL = env("CORECART_FRONTEND_URL", "").rstrip("/")

# --------------------------------------------------------------------------
# REST API
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",  # enforces CSRF
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "core.api.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("API_THROTTLE_ANON", "120/min"),
        "user": env("API_THROTTLE_USER", "1200/min"),
        "auth": env("API_THROTTLE_AUTH", "20/min"),
    },
    "EXCEPTION_HANDLER": "core.api.exceptions.api_exception_handler",
    # Number of trusted reverse proxies in front of the app. Throttling identifies clients by
    # REMOTE_ADDR when 0; otherwise by the matching X-Forwarded-For hop. Never trust a raw
    # client-supplied X-Forwarded-For (that lets anyone bypass the login rate limit).
    "NUM_PROXIES": int(env("DJANGO_NUM_PROXIES", "1" if env_bool("DJANGO_BEHIND_PROXY", False) else "0")),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append("rest_framework.renderers.BrowsableAPIRenderer")

# --------------------------------------------------------------------------
# Browser frontend on another origin (e.g. a React SPA)
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000" if DEBUG else "")
CORS_ALLOW_CREDENTIALS = True  # needed for the httpOnly refresh cookie / session cookie
CORS_URLS_REGEX = r"^/api/.*$"
CORS_ALLOW_HEADERS = (
    "accept", "authorization", "content-type", "origin", "user-agent", "x-csrftoken", "x-requested-with",
    "idempotency-key",
)
CORS_PREFLIGHT_MAX_AGE = 86400
# The SPA's origin must be trusted for CSRF-protected (session/cookie) requests.
CSRF_TRUSTED_ORIGINS = sorted(set(CSRF_TRUSTED_ORIGINS) | set(CORS_ALLOWED_ORIGINS))

# Refresh-token cookie for browser clients. When a login request is made with
# `"use_cookie": true`, the refresh token is set as an httpOnly cookie (never
# readable by JavaScript) and omitted from the JSON body.
JWT_REFRESH_COOKIE_NAME = env("JWT_REFRESH_COOKIE_NAME", "cc_refresh")
JWT_REFRESH_COOKIE_PATH = "/api/v1/auth/"
JWT_REFRESH_COOKIE_SECURE = env_bool("JWT_REFRESH_COOKIE_SECURE", not DEBUG)
# "Lax" works when the SPA and API share a site (app.example.com + api.example.com).
# Use "None" (with Secure) only if they are on entirely different sites.
JWT_REFRESH_COOKIE_SAMESITE = env("JWT_REFRESH_COOKIE_SAMESITE", "Lax")
JWT_REFRESH_COOKIE_DOMAIN = env("JWT_REFRESH_COOKIE_DOMAIN", "") or None

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Tokens carry a hash of the password: changing or resetting the password (API, site,
    # admin) invalidates every access and refresh token issued before the change.
    "CHECK_REVOKE_TOKEN": True,
    "TOKEN_REFRESH_SERIALIZER": "accounts.api.serializers.RevocableTokenRefreshSerializer",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CoreCart API",
    "DESCRIPTION": "REST API for the CoreCart multi-vendor marketplace. Authenticate with a JWT "
    "(`Authorization: Bearer <access>`) obtained from `/api/v1/auth/token/`, or with a session cookie + CSRF token.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "OrderStatusEnum": "orders.models.Order.Status",
        "TicketStatusEnum": "support.models.SupportTicket.Status",
        "ApprovalStatusEnum": "accounts.models.VendorProfile.Approval",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "WARNING")},
}
