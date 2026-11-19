"""
Checkout and order workflow.

Concurrency strategy
--------------------
* Everything runs inside ``transaction.atomic()``.
* Rows that are read-then-written (products, variants, coupons) are locked with
  ``select_for_update()``. On PostgreSQL this takes row locks. SQLite ignores it, but
  the SQLite connection uses ``transaction_mode=IMMEDIATE`` so each write
  transaction holds the database write lock from its first statement.
* Stock and coupon counters are additionally changed with *conditional* UPDATEs
  (``stock >= qty`` / ``used_count < usage_limit``). If the row count is 0 the
  whole transaction is rolled back, so overselling is impossible on either backend.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from cart.models import CartItem
from core.utils import money
from products.models import Product, ProductVariant
from products.services import notify_back_in_stock

from . import notifications
from .models import Coupon, CouponError, Order, OrderItem, OrderTimeline


class CheckoutError(Exception):
    """Checkout could not be completed; the message is user-facing."""


class OrderWorkflowError(Exception):
    """An order or item status change was rejected; the message is user-facing."""


@dataclass
class CheckoutSummary:
    items: list = field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    discount: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    coupon: Coupon | None = None
    coupon_error: str = ""
    problems: list = field(default_factory=list)

    @property
    def is_empty(self):
        return not self.items


def _active_cart_items(user):
    return list(
        CartItem.objects.filter(user=user, is_saved_for_later=False).select_related(
            "product__category", "product__vendor__user", "variant"
        )
    )


def find_coupon(code):
    code = (code or "").strip()
    if not code:
        return None
    return Coupon.objects.filter(code__iexact=code).first()


def build_checkout_summary(user, coupon_code=None):
    """Recalculate everything from the database for display on the checkout page."""
    summary = CheckoutSummary(items=_active_cart_items(user))
    for item in summary.items:
        summary.subtotal += item.subtotal
        if item.problem:
            summary.problems.append(f"{item.product.name}: {item.problem}")
    summary.subtotal = money(summary.subtotal)

    if coupon_code:
        coupon = find_coupon(coupon_code)
        if coupon is None:
            summary.coupon_error = "Invalid coupon code."
        else:
            try:
                coupon.validate_for(summary.subtotal)
                summary.coupon = coupon
                summary.discount = coupon.calculate_discount(summary.subtotal)
            except CouponError as exc:
                summary.coupon_error = str(exc)

    summary.total = money(summary.subtotal - summary.discount)
    return summary


def _record(order, status, note, actor=None):
    OrderTimeline.objects.create(order=order, status=status, note=note, actor=actor)


@transaction.atomic
def place_order(user, *, shipping, payment_method, coupon_code="", checkout_token, customer_note=""):
    """
    Turn the user's active cart into an order. Returns ``(order, created)``.

    A repeated submission with the same ``checkout_token`` returns the existing
    order instead of creating a second one.
    """
    existing = Order.objects.filter(checkout_token=checkout_token, user=user).first()
    if existing:
        return existing, False

    if payment_method not in {choice for choice, _ in Order.PaymentMethod.choices}:
        raise CheckoutError("Please choose a valid payment method.")

    items = _active_cart_items(user)
    if not items:
        raise CheckoutError("Your cart is empty.")

    # Lock the product and variant rows involved so prices/stock cannot change underneath us.
    product_ids = {item.product_id for item in items}
    variant_ids = {item.variant_id for item in items if item.variant_id}
    locked_products = {
        p.pk: p
        for p in Product.objects.select_for_update(of=("self",))
        .filter(pk__in=product_ids)
        .select_related("category", "vendor__user")
    }
    locked_variants = {v.pk: v for v in ProductVariant.objects.select_for_update().filter(pk__in=variant_ids)}

    lines = []
    subtotal = Decimal("0.00")
    for item in items:
        product = locked_products[item.product_id]
        variant = locked_variants.get(item.variant_id) if item.variant_id else None
        if not product.is_visible or (variant is not None and not variant.is_active):
            raise CheckoutError(f'"{product.name}" is no longer available. Please remove it from your cart.')
        if variant is None and product.variants.filter(is_active=True).exists():
            raise CheckoutError(f'Please choose an option for "{product.name}".')
        available = variant.stock if variant else product.stock
        if item.quantity > available:
            raise CheckoutError(
                f'Only {available} of "{product.name}" left in stock. Please update your cart.'
                if available
                else f'"{product.name}" is out of stock. Please remove it from your cart.'
            )
        unit_price = variant.price_override if variant and variant.price_override is not None else product.price
        subtotal += unit_price * item.quantity
        lines.append((item, product, variant, unit_price))
    subtotal = money(subtotal)

    coupon = None
    discount = Decimal("0.00")
    if coupon_code:
        coupon = Coupon.objects.select_for_update().filter(code__iexact=coupon_code.strip()).first()
        if coupon is None:
            raise CheckoutError("Invalid coupon code.")
        try:
            coupon.validate_for(subtotal)
        except CouponError as exc:
            raise CheckoutError(str(exc)) from exc
        discount = coupon.calculate_discount(subtotal)
        claimed = Coupon.objects.filter(pk=coupon.pk, used_count__lt=F("usage_limit")).update(
            used_count=F("used_count") + 1
        )
        if not claimed:
            raise CheckoutError("This coupon has reached its usage limit.")

    try:
        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                status=Order.Status.PENDING,
                payment_status=Order.PaymentStatus.UNPAID,
                payment_method=payment_method,
                subtotal_amount=subtotal,
                discount_amount=discount,
                total_amount=money(subtotal - discount),
                coupon=coupon,
                coupon_code=coupon.code if coupon else "",
                checkout_token=checkout_token,
                customer_note=customer_note,
                **{f"shipping_{key}": value for key, value in shipping.items()},
            )
    except IntegrityError:
        # Another request with the same token won the race.
        existing = Order.objects.filter(checkout_token=checkout_token, user=user).first()
        if existing:
            return existing, False
        raise

    order_items = []
    for item, product, variant, unit_price in lines:
        if variant is not None:
            updated = ProductVariant.objects.filter(pk=variant.pk, stock__gte=item.quantity).update(
                stock=F("stock") - item.quantity
            )
        else:
            updated = Product.objects.filter(pk=product.pk, stock__gte=item.quantity).update(
                stock=F("stock") - item.quantity
            )
        if not updated:
            raise CheckoutError(f'"{product.name}" just sold out. Please update your cart.')
        order_items.append(
            OrderItem(
                order=order,
                product=product,
                variant=variant,
                vendor=product.vendor,
                product_name=product.name,
                variant_label=variant.label if variant else "",
                quantity=item.quantity,
                price=unit_price,
                commission_rate=product.vendor.commission_rate if product.vendor else Decimal("0.00"),
                status=OrderItem.Status.PENDING,
            )
        )
    OrderItem.objects.bulk_create(order_items)

    _record(order, Order.Status.PENDING, f"Order placed. Payment method: {order.get_payment_method_display()}.", user)
    CartItem.objects.filter(pk__in=[item.pk for item, *_ in lines]).delete()

    transaction.on_commit(lambda: notifications.order_placed(order.pk))
    return order, True


def _restock(item):
    if item.variant_id:
        ProductVariant.objects.filter(pk=item.variant_id).update(stock=F("stock") + item.quantity)
    else:
        Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
    product_id = item.product_id
    transaction.on_commit(lambda: notify_back_in_stock(product_id))


def recalculate_totals(order):
    """Recompute amounts from non-cancelled lines after a partial cancellation."""
    subtotal = money(sum((i.subtotal for i in order.items.all() if i.status != OrderItem.Status.CANCELLED), Decimal()))
    if order.coupon_id and order.coupon:
        discount = order.coupon.calculate_discount(subtotal)
    else:
        discount = money(min(order.discount_amount, subtotal))
    order.subtotal_amount = subtotal
    order.discount_amount = discount
    order.total_amount = money(subtotal - discount)
    order.save(update_fields=["subtotal_amount", "discount_amount", "total_amount", "updated_at"])


def derive_order_status(statuses):
    """Parent order status from its item statuses (cancelled items are ignored unless all are)."""
    live = [s for s in statuses if s != OrderItem.Status.CANCELLED]
    if not live:
        return Order.Status.CANCELLED
    if all(s == OrderItem.Status.DELIVERED for s in live):
        return Order.Status.DELIVERED
    if all(s in (OrderItem.Status.SHIPPED, OrderItem.Status.DELIVERED) for s in live):
        return Order.Status.SHIPPED
    if any(s != OrderItem.Status.PENDING for s in live):
        return Order.Status.PROCESSING
    return Order.Status.PENDING


def sync_order_status(order, actor=None):
    new_status = derive_order_status(list(order.items.values_list("status", flat=True)))
    if new_status == order.status:
        return False
    old_label = order.get_status_display()
    order.status = new_status
    fields = ["status", "updated_at"]
    if new_status == Order.Status.CANCELLED:
        order.cancelled_at = timezone.now()
        fields.append("cancelled_at")
    order.save(update_fields=fields)
    _record(order, new_status, f"Order status changed from {old_label} to {order.get_status_display()}.", actor)
    transaction.on_commit(lambda: notifications.order_status_changed(order.pk))
    return True


def _release_coupon(order):
    if order.coupon_id:
        Coupon.objects.filter(pk=order.coupon_id, used_count__gt=0).update(used_count=F("used_count") - 1)


@transaction.atomic
def set_item_status(item, new_status, actor, tracking_number=None):
    """Move one order line through the fulfilment workflow."""
    item = OrderItem.objects.select_for_update().get(pk=item.pk)
    order = Order.objects.select_for_update().get(pk=item.order_id)

    if not item.can_transition_to(new_status):
        raise OrderWorkflowError(
            f"Cannot change an item from {item.get_status_display()} to {OrderItem.Status(new_status).label}."
        )
    if new_status == OrderItem.Status.CANCELLED and order.is_paid:
        raise OrderWorkflowError("This order has been paid. Contact an administrator to cancel and refund it.")

    tracking_number = (tracking_number or "").strip()
    if new_status == OrderItem.Status.SHIPPED and not (tracking_number or item.tracking_number):
        raise OrderWorkflowError("A tracking number is required to mark an item as shipped.")

    item.status = new_status
    if tracking_number:
        item.tracking_number = tracking_number
    item.save(update_fields=["status", "tracking_number", "updated_at"])

    note = f'"{item.display_name}" marked as {item.get_status_display()}.'
    if tracking_number:
        note += f" Tracking number: {tracking_number}."
    _record(order, order.status, note, actor)

    if new_status == OrderItem.Status.CANCELLED:
        _restock(item)
        recalculate_totals(order)
    if tracking_number and not order.tracking_number:
        order.tracking_number = tracking_number
        order.save(update_fields=["tracking_number", "updated_at"])

    status_changed = sync_order_status(order, actor)
    if order.status == Order.Status.CANCELLED and status_changed:
        _release_coupon(order)
    return item


@transaction.atomic
def cancel_order(order, actor, reason=""):
    """Cancel every remaining line, restock it and release the coupon."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.is_cancelled:
        raise OrderWorkflowError("This order is already cancelled.")
    if order.is_paid:
        raise OrderWorkflowError("Paid orders must be refunded before they can be cancelled.")
    items = list(order.items.select_for_update())
    if any(i.status in (OrderItem.Status.SHIPPED, OrderItem.Status.DELIVERED) for i in items):
        raise OrderWorkflowError("Orders with shipped items can no longer be cancelled.")

    for item in items:
        if item.status != OrderItem.Status.CANCELLED:
            item.status = OrderItem.Status.CANCELLED
            item.save(update_fields=["status", "updated_at"])
            _restock(item)

    order.status = Order.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.save(update_fields=["status", "cancelled_at", "updated_at"])
    _release_coupon(order)
    note = "Order cancelled."
    if reason:
        note += f" Reason: {reason}"
    _record(order, Order.Status.CANCELLED, note, actor)
    transaction.on_commit(lambda: notifications.order_status_changed(order.pk))
    return order
