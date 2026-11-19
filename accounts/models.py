from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.validators import IMAGE_VALIDATORS


class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        return super().create_superuser(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    """
    Platform user. ``role`` is only ever set on the server (registration views,
    Django admin) and never accepted from a public form.
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        VENDOR = "vendor", "Vendor"
        ADMIN = "admin", "Admin"

    ROLE_CHOICES = Role.choices

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
        help_text="User role determines access permissions",
    )
    email = models.EmailField(unique=True, help_text="Email must be unique")
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True, validators=IMAGE_VALIDATORS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_vendor(self):
        return self.role == self.Role.VENDOR

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_platform_admin(self):
        """Superusers, or staff accounts holding the admin role."""
        return self.is_active and (self.is_superuser or (self.is_admin_role and self.is_staff))

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def approved_vendor_profile(self):
        """The vendor profile when this user may currently sell, else ``None``."""
        if not self.is_vendor:
            return None
        profile = getattr(self, "vendor_profile", None)
        if profile is not None and profile.can_sell:
            return profile
        return None

    def get_dashboard_url(self):
        """Return the dashboard URL appropriate for the user's role."""
        if self.is_vendor:
            return reverse("accounts:vendor_dashboard")
        if self.is_platform_admin or self.is_admin_role:
            return reverse("analytics:admin_dashboard")
        return reverse("accounts:customer_dashboard")


class CustomerProfile(models.Model):
    """Customer details. The address stored here is the default delivery address."""

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="customer_profile",
        limit_choices_to={"role": "customer"},
    )
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default="USA")

    newsletter_subscribed = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer Profile"
        verbose_name_plural = "Customer Profiles"

    def __str__(self):
        return f"{self.user.username}'s Customer Profile"

    @property
    def full_address(self):
        parts = [self.address, self.city, self.state, self.zip_code, self.country]
        return ", ".join(filter(None, parts))

    @property
    def has_address(self):
        return bool(self.address and self.city)


class VendorProfile(models.Model):
    """Vendor business details and approval workflow (pending -> approved/rejected)."""

    class Approval(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    APPROVAL_STATUS = Approval.choices

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="vendor_profile",
        limit_choices_to={"role": "vendor"},
    )

    business_name = models.CharField(max_length=200, unique=True)
    business_description = models.TextField(blank=True)
    business_logo = models.ImageField(upload_to="vendor_logos/", blank=True, null=True, validators=IMAGE_VALIDATORS)
    business_banner = models.ImageField(
        upload_to="vendor_banners/", blank=True, null=True, validators=IMAGE_VALIDATORS
    )

    business_email = models.EmailField()
    business_phone = models.CharField(max_length=20)
    business_address = models.TextField()
    business_city = models.CharField(max_length=100)
    business_state = models.CharField(max_length=100)
    business_zip_code = models.CharField(max_length=20)
    business_country = models.CharField(max_length=100, default="USA")

    tax_id = models.CharField(max_length=50, blank=True, help_text="Tax ID or EIN")
    business_registration_number = models.CharField(max_length=100, blank=True)

    approval_status = models.CharField(max_length=20, choices=Approval.choices, default=Approval.PENDING)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_vendors",
    )
    rejection_reason = models.TextField(blank=True, help_text="Shown to the vendor when rejected or suspended.")

    store_slug = models.SlugField(max_length=200, unique=True)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Platform commission percentage (0-100)",
    )

    # Legacy denormalised metrics. They were never maintained; dashboards compute
    # live values from orders instead. Kept to avoid a destructive migration.
    total_products = models.PositiveIntegerField(default=0, editable=False)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    total_orders = models.PositiveIntegerField(default=0, editable=False)
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        editable=False,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vendor Profile"
        verbose_name_plural = "Vendor Profiles"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["approval_status"]),
            models.Index(fields=["store_slug"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(commission_rate__gte=0) & models.Q(commission_rate__lte=100),
                name="vendor_commission_rate_range",
            ),
        ]

    def __str__(self):
        return f"{self.business_name} ({self.get_approval_status_display()})"

    @property
    def is_approved(self):
        return self.approval_status == self.Approval.APPROVED

    @property
    def can_sell(self):
        """Only approved vendors with an active user account can publish and fulfil."""
        return self.is_approved and self.user.is_active

    def get_store_url(self):
        return reverse("accounts:vendor_store", kwargs={"slug": self.store_slug})

    def approve(self, by=None):
        self.approval_status = self.Approval.APPROVED
        self.approved_at = timezone.now()
        self.approved_by = by
        self.rejection_reason = ""
        self.save(update_fields=["approval_status", "approved_at", "approved_by", "rejection_reason", "updated_at"])

    def reject(self, by=None, reason=""):
        self.approval_status = self.Approval.REJECTED
        self.approved_at = None
        self.approved_by = by
        self.rejection_reason = reason
        self.save(update_fields=["approval_status", "approved_at", "approved_by", "rejection_reason", "updated_at"])

    def suspend(self, by=None, reason=""):
        self.approval_status = self.Approval.SUSPENDED
        self.approved_by = by
        self.rejection_reason = reason
        self.save(update_fields=["approval_status", "approved_by", "rejection_reason", "updated_at"])


class Wishlist(models.Model):
    """One wishlist per user. The M2M relation makes duplicate entries impossible."""

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="wishlist")
    products = models.ManyToManyField("products.Product", related_name="wishlisted_by", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"

    def __str__(self):
        return f"{self.user.username}'s Wishlist"
