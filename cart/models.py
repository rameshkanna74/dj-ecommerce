from django.conf import settings
from django.db import models
from django.db.models import Q

from products.models import Product, ProductVariant


class CartItem(models.Model):
    """A database-backed cart line. Prices are never stored here; they are read live."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    is_saved_for_later = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="cartitem_quantity_positive"),
            models.UniqueConstraint(
                fields=["user", "product"], condition=Q(variant__isnull=True), name="cartitem_unique_product"
            ),
            models.UniqueConstraint(
                fields=["user", "product", "variant"],
                condition=Q(variant__isnull=False),
                name="cartitem_unique_variant",
            ),
        ]
        indexes = [models.Index(fields=["user", "is_saved_for_later"])]

    def __str__(self):
        status = " (Saved)" if self.is_saved_for_later else ""
        return f"{self.quantity}x {self.product.name}{status}"

    @property
    def unit_price(self):
        # Avoid variant.current_price here: it would re-fetch variant.product per line.
        if self.variant_id and self.variant.price_override is not None:
            return self.variant.price_override
        return self.product.price

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    @property
    def available_stock(self):
        return self.variant.stock if self.variant_id else self.product.stock

    @property
    def is_purchasable(self):
        variant_ok = self.variant_id is None or self.variant.is_active
        return self.product.is_visible and variant_ok and self.available_stock > 0

    @property
    def problem(self):
        """Human-readable reason this line cannot be checked out, or ''."""
        if not self.product.is_visible or (self.variant_id and not self.variant.is_active):
            return "This product is no longer available."
        if self.available_stock <= 0:
            return "Out of stock."
        if self.quantity > self.available_stock:
            return f"Only {self.available_stock} left in stock."
        return ""
