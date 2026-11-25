import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from core.utils import money
from products.models import Product, ProductVariant


class CouponError(Exception):
    """Raised when a coupon cannot be applied; the message is user-facing."""


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed Amount"

    DISCOUNT_CHOICES = DiscountType.choices

    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Percentage (1-100) or fixed amount",
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Minimum cart subtotal required to use this coupon",
    )
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=100, help_text="Maximum number of times this coupon can be used")
    used_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-valid_to"]
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="coupon_value_positive"),
            models.CheckConstraint(
                condition=Q(discount_type="fixed") | Q(value__lte=100), name="coupon_percentage_max_100"
            ),
            models.CheckConstraint(condition=Q(valid_to__gt=F("valid_from")), name="coupon_valid_range"),
            models.CheckConstraint(condition=Q(used_count__lte=F("usage_limit")), name="coupon_usage_within_limit"),
        ]

    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()})"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_valid(self, now=None):
        now = now or timezone.now()
        return self.active and self.valid_from <= now <= self.valid_to and self.used_count < self.usage_limit

    def validate_for(self, subtotal, now=None):
        now = now or timezone.now()
        if not self.active:
            raise CouponError("This coupon is not active.")
        if now < self.valid_from:
            raise CouponError("This coupon is not valid yet.")
        if now > self.valid_to:
            raise CouponError("This coupon has expired.")
        if self.used_count >= self.usage_limit:
            raise CouponError("This coupon has reached its usage limit.")
        if subtotal < self.min_order_amount:
            raise CouponError(f"This coupon requires a minimum order of {self.min_order_amount}.")

    def calculate_discount(self, subtotal):
        """Discount for ``subtotal``; never negative and never more than the subtotal."""
        subtotal = money(subtotal)
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = subtotal * self.value / Decimal("100")
        else:
            discount = self.value
        return money(min(max(discount, Decimal("0")), subtotal))


def generate_order_number():
    return f"CC{timezone.now():%y%m%d}{secrets.token_hex(3).upper()}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Awaiting payment"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    class PaymentMethod(models.TextChoices):
        COD = "cod", "Cash on delivery"
        BANK_TRANSFER = "bank_transfer", "Bank transfer (manual confirmation)"

    STATUS_CHOICES = Status.choices
    PROGRESS_STEPS = [Status.PENDING, Status.PROCESSING, Status.SHIPPED, Status.DELIVERED]

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    # Legacy guest-checkout fields. Checkout requires an account; kept for history.
    guest_email = models.EmailField(null=True, blank=True)
    guest_name = models.CharField(max_length=100, null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    coupon_code = models.CharField(max_length=50, blank=True)

    # Delivery address snapshot
    shipping_full_name = models.CharField(max_length=150, blank=True)
    shipping_phone = models.CharField(max_length=20, blank=True)
    shipping_address = models.TextField(blank=True)
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    shipping_country = models.CharField(max_length=100, blank=True)
    customer_note = models.TextField(blank=True)

    tracking_number = models.CharField(max_length=100, blank=True)
    checkout_token = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["payment_status", "status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="order_total_non_negative"),
            models.CheckConstraint(condition=Q(discount_amount__gte=0), name="order_discount_non_negative"),
            models.CheckConstraint(condition=Q(subtotal_amount__gte=0), name="order_subtotal_non_negative"),
        ]

    def __str__(self):
        identifier = self.user.username if self.user else f"Guest ({self.guest_email})"
        return f"Order {self.order_number} - {identifier}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            number = generate_order_number()
            while Order.objects.filter(order_number=number).exists():
                number = generate_order_number()
            self.order_number = number
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("orders:detail", kwargs={"order_number": self.order_number})

    @property
    def is_paid(self):
        return self.payment_status == self.PaymentStatus.PAID

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    @property
    def customer_email(self):
        return self.user.email if self.user else self.guest_email

    @property
    def customer_name(self):
        if self.shipping_full_name:
            return self.shipping_full_name
        if self.user:
            return self.user.display_name
        return self.guest_name or "Guest"

    @property
    def shipping_lines(self):
        city_line = " ".join(filter(None, [self.shipping_city, self.shipping_state, self.shipping_postal_code]))
        return [line for line in [self.shipping_address, city_line, self.shipping_country] if line]

    @property
    def progress_index(self):
        try:
            return self.PROGRESS_STEPS.index(self.status)
        except ValueError:
            return -1

    def can_customer_cancel(self):
        """Customers may cancel unpaid orders before any item has started processing."""
        if self.status != self.Status.PENDING or self.is_paid:
            return False
        return not self.items.exclude(status__in=[OrderItem.Status.PENDING, OrderItem.Status.CANCELLED]).exists()


class OrderItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    STATUS_CHOICES = Status.choices

    # Fulfilment workflow: Pending -> Processing -> Shipped -> Delivered.
    # Items can be cancelled until they ship.
    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.PROCESSING, Status.CANCELLED},
        Status.PROCESSING: {Status.SHIPPED, Status.CANCELLED},
        Status.SHIPPED: {Status.DELIVERED},
        Status.DELIVERED: set(),
        Status.CANCELLED: set(),
    }

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    # PROTECT: a sold option must stay linked so cancellations restock the right variant.
    # Vendors deactivate options that have orders instead of deleting them.
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="order_items"
    )
    vendor = models.ForeignKey(
        "accounts.VendorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        help_text="The vendor who owned the product at the time of purchase.",
    )
    # Immutable purchase-time snapshots
    product_name = models.CharField(max_length=200, blank=True)
    variant_label = models.CharField(max_length=120, blank=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["vendor", "status"])]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="orderitem_quantity_positive"),
            models.CheckConstraint(condition=Q(price__gte=0), name="orderitem_price_non_negative"),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.display_name}"

    @property
    def display_name(self):
        return self.product_name or self.product.name

    @property
    def subtotal(self):
        return self.quantity * self.price

    @property
    def commission_amount(self):
        return money(self.subtotal * self.commission_rate / Decimal("100"))

    @property
    def vendor_earnings(self):
        return self.subtotal - self.commission_amount

    def allowed_next_statuses(self):
        return self.ALLOWED_TRANSITIONS.get(self.status, set())

    def can_transition_to(self, status):
        return status in self.allowed_next_statuses()


class OrderTimeline(models.Model):
    """Append-only log of order events."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="timeline")
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-timestamp", "-id"]

    def __str__(self):
        return f"{self.order.order_number} - {self.status} at {self.timestamp}"
