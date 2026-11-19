from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, Exists, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse

from core.utils import unique_slugify
from core.validators import IMAGE_VALIDATORS

# Slugs that would shadow fixed URL paths under /products/.
RESERVED_SLUGS = {"new", "edit", "delete", "vendor"}


class CategoryQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, help_text="Inactive categories and their products are hidden.")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]
        indexes = [models.Index(fields=["slug"])]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"{reverse('products:list')}?category={self.slug}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def visible(self):
        """Products a shopper may see and buy: active, in an active category, sold by an
        approved vendor with an active account (or by the platform itself)."""
        return self.filter(
            Q(vendor__isnull=True) | Q(vendor__approval_status="approved", vendor__user__is_active=True),
            is_active=True,
            category__is_active=True,
        )

    def in_stock(self):
        active_variant_in_stock = ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True, stock__gt=0)
        return self.filter(Q(stock__gt=0) | Exists(active_variant_in_stock))

    def by_category(self, category_slug):
        return self.filter(category__slug=category_slug)

    def by_vendor(self, vendor):
        return self.filter(vendor=vendor)

    def search(self, query):
        query = (query or "").strip()
        if not query:
            return self
        return self.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query)
        )

    def with_units_sold(self):
        """Annotate ``units_sold`` from non-cancelled order lines of non-cancelled orders."""
        return self.annotate(
            units_sold=Coalesce(
                Sum(
                    "order_items__quantity",
                    filter=~Q(order_items__status="cancelled") & ~Q(order_items__order__status="cancelled"),
                ),
                Value(0),
            )
        )

    def for_listing(self):
        return self.select_related("category", "vendor")


ProductManager = models.Manager.from_queryset(ProductQuerySet)


class Product(models.Model):
    vendor = models.ForeignKey(
        "accounts.VendorProfile",
        on_delete=models.CASCADE,
        related_name="products",
        null=True,
        blank=True,
        help_text="The vendor who owns this product. Empty for products sold by CoreCart itself.",
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Shown in the homepage featured section.")
    cover_image = models.ImageField(upload_to="products/", blank=True, null=True, validators=IMAGE_VALIDATORS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Cached review metrics maintained by products.signals.
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_count = models.PositiveIntegerField(default=0)

    objects = ProductManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["price"]),
            models.Index(fields=["is_featured", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name="product_price_non_negative"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name, reserved=RESERVED_SLUGS)
        super().save(*args, **kwargs)

    @property
    def active_variants(self):
        # Uses the prefetch cache when the view prefetched variants.
        return [variant for variant in self.variants.all() if variant.is_active]

    @property
    def has_variants(self):
        return bool(self.active_variants)

    @property
    def total_available_stock(self):
        if self.has_variants:
            return sum(variant.stock for variant in self.active_variants)
        return self.stock

    @property
    def is_in_stock(self):
        return self.total_available_stock > 0

    @property
    def is_low_stock(self):
        return 0 < self.total_available_stock <= 5

    @property
    def is_visible(self):
        vendor_ok = self.vendor_id is None or self.vendor.can_sell
        return self.is_active and self.category.is_active and vendor_ok

    def update_rating(self):
        """Recalculate cached rating metrics from visible reviews."""
        stats = self.reviews.filter(is_visible=True).aggregate(avg=Avg("rating"), count=Count("id"))
        self.review_count = stats["count"] or 0
        self.average_rating = round(stats["avg"] or 0, 2)
        Product.objects.filter(pk=self.pk).update(average_rating=self.average_rating, review_count=self.review_count)


class ProductImage(models.Model):
    """Additional gallery images for a product."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/gallery/", validators=IMAGE_VALIDATORS)
    alt_text = models.CharField(max_length=200, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Image {self.position} for {self.product.name}"


class ProductVariant(models.Model):
    """Variations like Size or Color. A variant tracks its own stock and optional price."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute_name = models.CharField(max_length=50, help_text="e.g. 'Size' or 'Color'")
    attribute_value = models.CharField(max_length=50, help_text="e.g. 'Large' or 'Red'")
    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Optional price for this variant",
    )
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("product", "attribute_name", "attribute_value")
        ordering = ["attribute_name", "attribute_value"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price_override__isnull=True) | Q(price_override__gte=0),
                name="variant_price_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.label}"

    @property
    def label(self) -> str:
        return f"{self.attribute_name}: {self.attribute_value}"

    @property
    def current_price(self):
        return self.price_override if self.price_override is not None else self.product.price


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True, help_text="Uncheck to hide a review during moderation.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("product", "user")
        constraints = [
            models.CheckConstraint(condition=Q(rating__gte=1) & Q(rating__lte=5), name="review_rating_1_to_5"),
        ]

    def __str__(self):
        return f"Review for {self.product.name} by {self.user.username}"


class StockAlert(models.Model):
    """A request to be emailed once when a product comes back in stock."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stock_alerts")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_alerts")
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "product")
        indexes = [models.Index(fields=["product", "notified_at"])]

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class ProductQuestion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="questions")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="questions")
    question = models.TextField()
    answer = models.TextField(blank=True)
    is_answered = models.BooleanField(default=False)
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="answered_questions",
    )
    answered_at = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=True, help_text="Uncheck to hide during moderation.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Question on {self.product.name} by {self.user.username}"
