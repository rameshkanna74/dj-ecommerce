"""
Payment integration boundary.

CoreCart 1.0 ships only *offline* payment methods (cash on delivery and bank
transfer). Creating an order never marks it as paid; an administrator records the
payment once the money is actually received. A real gateway can later implement
``start_payment`` (redirect to the provider) and call ``mark_order_paid`` from its
verified webhook, without touching order creation.
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Order, OrderTimeline


class PaymentError(Exception):
    pass


PAYMENT_INSTRUCTIONS = {
    Order.PaymentMethod.COD: "Pay the courier in cash when your order is delivered.",
    Order.PaymentMethod.BANK_TRANSFER: (
        "Transfer the order total to our bank account using your order number as the reference. "
        "Your order is processed once the transfer is confirmed."
    ),
}


def available_payment_methods():
    enabled = set(settings.CORECART_PAYMENT_METHODS)
    return [(value, label) for value, label in Order.PaymentMethod.choices if value in enabled]


def payment_instructions(order):
    return PAYMENT_INSTRUCTIONS.get(order.payment_method, "")


def start_payment(order):
    """Offline methods need no redirect. A gateway integration would return its URL here."""
    if order.payment_method not in dict(available_payment_methods()):
        raise PaymentError("This payment method is not available.")
    return None


@transaction.atomic
def mark_order_paid(order, actor, reference=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.is_cancelled:
        raise PaymentError("Cancelled orders cannot be marked as paid.")
    if order.is_paid:
        return order
    order.payment_status = Order.PaymentStatus.PAID
    order.paid_at = timezone.now()
    order.payment_reference = reference
    order.save(update_fields=["payment_status", "paid_at", "payment_reference", "updated_at"])
    note = "Payment received."
    if reference:
        note += f" Reference: {reference}."
    OrderTimeline.objects.create(order=order, status=order.status, note=note, actor=actor)
    return order


@transaction.atomic
def mark_order_refunded(order, actor, note=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.is_paid:
        raise PaymentError("Only paid orders can be refunded.")
    order.payment_status = Order.PaymentStatus.REFUNDED
    order.save(update_fields=["payment_status", "updated_at"])
    OrderTimeline.objects.create(
        order=order, status=order.status, note=f"Payment refunded. {note}".strip(), actor=actor
    )
    return order
