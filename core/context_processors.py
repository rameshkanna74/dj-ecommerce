from django.conf import settings
from django.core.cache import cache

NAV_CATEGORIES_CACHE_KEY = "core:nav_categories"


def nav_categories():
    """Active categories for navigation. Cached; invalidated by products.signals."""
    categories = cache.get(NAV_CATEGORIES_CACHE_KEY)
    if categories is None:
        from products.models import Category

        categories = list(Category.objects.active().only("name", "slug"))
        cache.set(NAV_CATEGORIES_CACHE_KEY, categories, 60 * 60)
    return categories


def marketplace(request):
    """Global template context: cart badge, navigation categories and currency."""
    cart_count = 0
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_customer:
        from cart.services import active_cart_quantity

        cart_count = active_cart_quantity(user)
    return {
        "cart_count": cart_count,
        "nav_categories": nav_categories(),
        "currency_symbol": settings.CORECART_CURRENCY_SYMBOL,
    }
