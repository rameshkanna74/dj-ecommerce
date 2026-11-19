"""
httpOnly refresh-token cookie for browser clients (e.g. a React SPA).

Flow: the SPA logs in with ``{"use_cookie": true}``. The response body carries only the
short-lived ``access`` token (kept in memory); the refresh token is stored in an httpOnly
cookie scoped to ``/api/v1/auth/``. To refresh or log out, the SPA POSTs without a body
token and with the header ``X-Requested-With: XMLHttpRequest``. The header requirement
blocks cross-site form submissions, which cannot set custom headers.
"""

from django.conf import settings
from rest_framework.exceptions import PermissionDenied

CSRF_HEADER = "HTTP_X_REQUESTED_WITH"


def wants_cookie(request):
    value = request.data.get("use_cookie") if hasattr(request, "data") else None
    return value in (True, "true", "1", 1, "on")


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.JWT_REFRESH_COOKIE_PATH,
        domain=settings.JWT_REFRESH_COOKIE_DOMAIN,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response):
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        domain=settings.JWT_REFRESH_COOKIE_DOMAIN,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )


def move_refresh_to_cookie(response):
    """Move ``refresh`` from a JSON response body into the httpOnly cookie."""
    refresh = response.data.pop("refresh", None)
    if refresh:
        set_refresh_cookie(response, refresh)
    return response


def refresh_from_request(request):
    """
    Return ``(token, from_cookie)``. Body tokens win (mobile/server clients); otherwise the
    cookie is used, which requires the X-Requested-With header.
    """
    token = request.data.get("refresh") if hasattr(request.data, "get") else None
    if token:
        return token, False
    token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
    if token and not request.META.get(CSRF_HEADER):
        raise PermissionDenied("Cookie-based token requests must send the X-Requested-With header.")
    return token, bool(token)
