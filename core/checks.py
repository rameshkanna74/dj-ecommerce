"""Deployment checks specific to CoreCart. Run with `python manage.py check --deploy`."""

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security, deploy=True)
def corecart_deploy_checks(app_configs, **kwargs):
    issues = []
    backend = settings.CACHES["default"]["BACKEND"]
    if backend.endswith("LocMemCache"):
        issues.append(
            Warning(
                "The cache is per-process (LocMemCache). API rate limits and cached data are not shared "
                "between workers.",
                hint="Set REDIS_URL (install the `production` extra).",
                id="corecart.W001",
            )
        )
    if not settings.CORS_ALLOWED_ORIGINS:
        issues.append(
            Warning(
                "CORS_ALLOWED_ORIGINS is empty, so a browser frontend on another origin cannot call the API.",
                hint="Set CORS_ALLOWED_ORIGINS=https://app.example.com (ignore if no browser frontend uses the API).",
                id="corecart.W002",
            )
        )
    if any(origin.startswith("http://") for origin in settings.CORS_ALLOWED_ORIGINS):
        issues.append(
            Warning("CORS_ALLOWED_ORIGINS contains a non-HTTPS origin.", id="corecart.W003")
        )
    if settings.JWT_REFRESH_COOKIE_SAMESITE.lower() == "none" and not settings.JWT_REFRESH_COOKIE_SECURE:
        issues.append(
            Error("JWT_REFRESH_COOKIE_SAMESITE=None requires JWT_REFRESH_COOKIE_SECURE=True.", id="corecart.E001")
        )
    if settings.ADMIN_URL == "admin/":
        issues.append(
            Warning("The Django admin is at the default /admin/ URL.", hint="Set DJANGO_ADMIN_URL.",
                    id="corecart.W004")
        )
    return issues
