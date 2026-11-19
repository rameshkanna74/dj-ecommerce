"""Small shared helpers used across apps."""

from decimal import ROUND_HALF_UP, Decimal

from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify

CENT = Decimal("0.01")


def money(value):
    """Quantize a numeric value to two decimal places using bankers-safe rounding."""
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def unique_slugify(instance, value, slug_field="slug", max_length=200, reserved=()):
    """
    Return a slug for ``instance`` derived from ``value`` that is unique within the
    model's table. Appends ``-2``, ``-3`` ... on collision. Excludes the instance
    itself so re-saving an object keeps its slug.
    """
    base = slugify(value)[: max_length - 8].strip("-") or "item"
    model = type(instance)
    queryset = model._default_manager.all()
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    candidate = base
    counter = 2
    while candidate in reserved or queryset.filter(**{slug_field: candidate}).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def safe_redirect_target(request, candidate, fallback):
    """Return ``candidate`` only if it is a safe, same-host URL; otherwise ``fallback``."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return fallback
