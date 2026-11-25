"""
Small cache-based rate limiting for the server-rendered auth pages.

The API uses DRF throttles; these helpers give the HTML login and password-reset forms
the same protection. Clients are identified exactly like DRF does (REMOTE_ADDR, or the
trusted X-Forwarded-For hop when ``REST_FRAMEWORK["NUM_PROXIES"]`` > 0), so a spoofed
header cannot be used to dodge the limit. Uses the shared cache (Redis in production).
"""

from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


def client_ip(request):
    num_proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES") or 0
    forwarded = request.headers.get("x-forwarded-for")
    if num_proxies and forwarded:
        hops = [hop.strip() for hop in forwarded.split(",")]
        return hops[-min(num_proxies, len(hops))]
    return request.META.get("REMOTE_ADDR", "")


def _key(scope, ident):
    return f"ratelimit:{scope}:{ident}"


def is_limited(scope, ident, limit):
    return (cache.get(_key(scope, ident)) or 0) >= limit


def register_hit(scope, ident, window):
    key = _key(scope, ident)
    if cache.add(key, 1, timeout=window):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, timeout=window)
        return 1


def ratelimit_post(scope, limit, window):
    """Allow at most ``limit`` POSTs per client IP every ``window`` seconds (then HTTP 429)."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST":
                ident = client_ip(request)
                if is_limited(scope, ident, limit):
                    return HttpResponse("Too many requests. Please try again later.", status=429)
                register_hit(scope, ident, window)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
