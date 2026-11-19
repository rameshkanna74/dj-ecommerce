"""Cart business rules. Every amount is recalculated from the database."""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum

from .models import CartItem

MAX_QUANTITY_PER_LINE = 99


class CartError(Exception):
    """A cart operation was rejected; the message is safe to show to the user."""


@dataclass
class CartSummary:
    items: list = field(default_factory=list)
    saved_items: list = field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    total_quantity: int = 0
    has_problems: bool = False

    @property
    def is_empty(self):
        return not self.items


def cart_queryset(user):
    return CartItem.objects.filter(user=user).select_related(
        "product__category", "product__vendor__user", "variant"
    )


def get_cart_summary(user):
    summary = CartSummary()
    for item in cart_queryset(user):
        if item.is_saved_for_later:
            summary.saved_items.append(item)
            continue
        summary.items.append(item)
        summary.subtotal += item.subtotal
        summary.total_quantity += item.quantity
        if item.problem:
            summary.has_problems = True
    return summary


def active_cart_quantity(user):
    total = CartItem.objects.filter(user=user, is_saved_for_later=False).aggregate(total=Sum("quantity"))["total"]
    return total or 0


def _validate_purchasable(product, variant):
    if not product.is_visible:
        raise CartError("This product is not available for purchase.")
    if product.has_variants and variant is None:
        raise CartError("Please choose an option before adding this product to your cart.")
    if variant is not None and (variant.product_id != product.pk or not variant.is_active):
        raise CartError("The selected option is not available.")


def _validate_quantity(quantity, available):
    if quantity < 1:
        raise CartError("Quantity must be at least 1.")
    if quantity > MAX_QUANTITY_PER_LINE:
        raise CartError(f"You can buy at most {MAX_QUANTITY_PER_LINE} of an item per order.")
    if available <= 0:
        raise CartError("This item is out of stock.")
    if quantity > available:
        raise CartError(f"Only {available} left in stock.")


@transaction.atomic
def add_to_cart(user, product, quantity=1, variant=None):
    """Add ``quantity`` of a product (or move it back from saved-for-later). Returns the line."""
    _validate_purchasable(product, variant)
    available = variant.stock if variant else product.stock

    item = CartItem.objects.select_for_update().filter(user=user, product=product, variant=variant).first()
    if item is None:
        _validate_quantity(quantity, available)
        try:
            with transaction.atomic():
                return CartItem.objects.create(user=user, product=product, variant=variant, quantity=quantity)
        except IntegrityError:  # concurrent duplicate add; fall through to update
            item = CartItem.objects.select_for_update().get(user=user, product=product, variant=variant)

    new_quantity = quantity if item.is_saved_for_later else item.quantity + quantity
    _validate_quantity(new_quantity, available)
    item.quantity = new_quantity
    item.is_saved_for_later = False
    item.save(update_fields=["quantity", "is_saved_for_later", "updated_at"])
    return item


def update_quantity(item, quantity):
    _validate_quantity(quantity, item.available_stock)
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


def set_saved_for_later(item, saved):
    if not saved:
        _validate_purchasable(item.product, item.variant)
        if item.quantity > item.available_stock:
            if item.available_stock <= 0:
                raise CartError("This item is out of stock.")
            item.quantity = item.available_stock
    item.is_saved_for_later = saved
    item.save(update_fields=["is_saved_for_later", "quantity", "updated_at"])
    return item
