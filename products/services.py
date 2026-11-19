from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from core.emails import absolute_url, send_templated_email

from .models import Product, StockAlert


SORT_ORDERINGS = {
    "price_asc": ("price", "-created_at"),
    "price_desc": ("-price", "-created_at"),
    "rating": ("-average_rating", "-review_count", "-created_at"),
    "newest": ("-created_at",),
}


def filter_catalogue(queryset, data):
    """
    Apply validated ``ProductFilterForm`` data (q, category, min_price, max_price,
    in_stock, sort) to a product queryset. Shared by the HTML catalogue and the API.
    """
    queryset = queryset.search(data.get("q"))
    if data.get("category"):
        queryset = queryset.filter(category__slug=data["category"])
    if data.get("min_price") is not None:
        queryset = queryset.filter(price__gte=data["min_price"])
    if data.get("max_price") is not None:
        queryset = queryset.filter(price__lte=data["max_price"])
    if data.get("in_stock"):
        queryset = queryset.in_stock()
    sort = data.get("sort") or "newest"
    if sort == "popular":
        return queryset.with_units_sold().order_by("-units_sold", "-created_at")
    return queryset.order_by(*SORT_ORDERINGS.get(sort, SORT_ORDERINGS["newest"]))


def notify_back_in_stock(product_id):
    """
    Email every subscriber who has not been notified yet, once the product is
    purchasable again. ``notified_at`` guarantees one email per subscription.
    """
    product = Product.objects.visible().select_related("category", "vendor__user").filter(pk=product_id).first()
    if product is None or not product.is_in_stock:
        return 0

    sent = 0
    with transaction.atomic():
        alerts = list(
            StockAlert.objects.select_for_update(of=("self",))
            .filter(product=product, notified_at__isnull=True)
            .select_related("user")
        )
        if not alerts:
            return 0
        StockAlert.objects.filter(pk__in=[alert.pk for alert in alerts]).update(notified_at=timezone.now())

    url = absolute_url(reverse("products:detail", kwargs={"slug": product.slug}))
    for alert in alerts:
        if alert.user.is_active:
            sent += send_templated_email("back_in_stock", {"user": alert.user, "product": product, "url": url},
                                         [alert.user.email])
    return sent


def subscribe_stock_alert(user, product):
    """Create or re-arm a stock alert. Returns (alert, created)."""
    alert, created = StockAlert.objects.get_or_create(user=user, product=product)
    if not created and alert.notified_at is not None:
        alert.notified_at = None
        alert.save(update_fields=["notified_at"])
        created = True
    return alert, created


def user_has_purchased(user, product):
    from orders.models import OrderItem

    return OrderItem.objects.filter(
        order__user=user, product=product, status=OrderItem.Status.DELIVERED
    ).exists()
