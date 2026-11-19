from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from core.emails import absolute_url, send_templated_email

from .models import Product, StockAlert


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
