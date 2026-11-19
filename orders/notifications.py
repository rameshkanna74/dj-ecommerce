from django.urls import reverse

from core.emails import absolute_url, send_templated_email

from .models import Order


def _order(order_id):
    return Order.objects.select_related("user").prefetch_related("items").filter(pk=order_id).first()


def _wants_email(order):
    profile = getattr(order.user, "customer_profile", None) if order.user else None
    return profile is None or profile.email_notifications


def order_placed(order_id):
    order = _order(order_id)
    if order is None:
        return 0
    url = absolute_url(reverse("orders:detail", kwargs={"order_number": order.order_number}))
    sent = send_templated_email("order_placed", {"order": order, "url": url}, [order.customer_email])

    vendors = {}
    for item in order.items.select_related("vendor__user"):
        if item.vendor:
            vendors.setdefault(item.vendor, []).append(item)
    for vendor, items in vendors.items():
        vendor_url = absolute_url(reverse("orders:vendor_order_detail", kwargs={"order_number": order.order_number}))
        sent += send_templated_email(
            "vendor_new_order",
            {"order": order, "vendor": vendor, "items": items, "url": vendor_url},
            [vendor.business_email or vendor.user.email],
        )
    return sent


def order_status_changed(order_id):
    order = _order(order_id)
    if order is None or not _wants_email(order):
        return 0
    url = absolute_url(reverse("orders:detail", kwargs={"order_number": order.order_number}))
    return send_templated_email("order_status", {"order": order, "url": url}, [order.customer_email])
