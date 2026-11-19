from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()


@register.filter
def money(value):
    """Format a numeric value as currency, e.g. ``$1,234.50``."""
    try:
        amount = Decimal(value or 0).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return value
    sign = "-" if amount < 0 else ""
    whole, _, cents = f"{abs(amount):.2f}".partition(".")
    return f"{sign}{settings.CORECART_CURRENCY_SYMBOL}{intcomma(int(whole))}.{cents}"


@register.simple_tag(takes_context=True)
def query_string(context, **updates):
    """Return the current query string with ``updates`` applied (None removes a key)."""
    params = context["request"].GET.copy()
    for key, value in updates.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"


STATUS_TONES = {
    "pending": "warning",
    "processing": "info",
    "shipped": "info",
    "delivered": "success",
    "cancelled": "danger",
    "unpaid": "warning",
    "paid": "success",
    "refunded": "neutral",
    "approved": "success",
    "rejected": "danger",
    "suspended": "danger",
    "open": "warning",
    "in_progress": "info",
    "resolved": "success",
    "closed": "neutral",
}


@register.filter
def status_tone(value):
    return STATUS_TONES.get(str(value), "neutral")


@register.filter
def stars(value):
    """Return a list of 5 booleans for rendering filled/empty stars."""
    try:
        rating = float(value or 0)
    except (TypeError, ValueError):
        rating = 0
    return [index < round(rating) for index in range(5)]


@register.simple_tag(takes_context=True)
def active_link(context, *url_names):
    """Return 'is-active' when the current URL name matches any given name."""
    match = getattr(context.get("request"), "resolver_match", None)
    if match and match.view_name in url_names:
        return "is-active"
    return ""
