import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from accounts.models import CustomUser, VendorProfile
from cart.models import CartItem
from orders.models import Coupon
from products.models import Category, Product, ProductVariant

PASSWORD = "Str0ng-Pass!word"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def make_user(username, role=CustomUser.Role.CUSTOMER, **extra):
    return CustomUser.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD, role=role, **extra
    )


def make_vendor(username, status=VendorProfile.Approval.APPROVED, commission="10.00"):
    user = make_user(username, role=CustomUser.Role.VENDOR)
    return VendorProfile.objects.create(
        user=user,
        business_name=f"{username.title()} Goods",
        business_email=f"{username}-biz@example.com",
        business_phone="5550100",
        business_address="1 Market St",
        business_city="Springfield",
        business_state="IL",
        business_zip_code="62701",
        store_slug=f"{username}-goods",
        approval_status=status,
        commission_rate=Decimal(commission),
    )


@pytest.fixture
def customer(db):
    return make_user("alice", first_name="Alice", last_name="Smith")


@pytest.fixture
def other_customer(db):
    return make_user("bob")


@pytest.fixture
def vendor(db):
    return make_vendor("vera")


@pytest.fixture
def other_vendor(db):
    return make_vendor("victor")


@pytest.fixture
def pending_vendor(db):
    return make_vendor("penny", status=VendorProfile.Approval.PENDING)


@pytest.fixture
def admin_user(db):
    return CustomUser.objects.create_superuser(username="root", email="root@example.com", password=PASSWORD)


@pytest.fixture
def category(db):
    return Category.objects.create(name="Kitchen", description="Cook better")


@pytest.fixture
def make_product(category, vendor):
    def _make(name="Chef Knife", price="25.00", stock=10, owner=vendor, **extra):
        return Product.objects.create(
            name=name,
            description=f"{name} description",
            price=Decimal(price),
            stock=stock,
            category=extra.pop("category", category),
            vendor=owner,
            **extra,
        )

    return _make


@pytest.fixture
def product(make_product):
    return make_product()


@pytest.fixture
def variant_product(make_product):
    product = make_product(name="Linen Apron", price="30.00", stock=0)
    small = ProductVariant.objects.create(product=product, attribute_name="Size", attribute_value="S", stock=3)
    large = ProductVariant.objects.create(
        product=product, attribute_name="Size", attribute_value="L", stock=2, price_override=Decimal("35.00")
    )
    return product, small, large


@pytest.fixture
def make_coupon(db):
    def _make(code="SAVE10", discount_type="percentage", value="10.00", **extra):
        now = timezone.now()
        defaults = {
            "valid_from": now - timedelta(days=1),
            "valid_to": now + timedelta(days=30),
            "usage_limit": 100,
        }
        defaults.update(extra)
        return Coupon.objects.create(code=code, discount_type=discount_type, value=Decimal(value), **defaults)

    return _make


@pytest.fixture
def login(client):
    def _login(user):
        client.force_login(user)
        return client

    return _login


@pytest.fixture
def customer_client(login, customer):
    return login(customer)


@pytest.fixture
def vendor_client(login, vendor):
    return login(vendor.user)


@pytest.fixture
def admin_client_(login, admin_user):
    return login(admin_user)


@pytest.fixture
def fill_cart():
    def _fill(user, product, quantity=1, variant=None, saved=False):
        return CartItem.objects.create(
            user=user, product=product, quantity=quantity, variant=variant, is_saved_for_later=saved
        )

    return _fill


@pytest.fixture
def api():
    """Factory for DRF APIClients, optionally authenticated as ``user``."""
    from rest_framework.test import APIClient

    def _client(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return _client


SHIPPING = {
    "full_name": "Alice Smith",
    "phone": "+1 555 0100",
    "address": "742 Evergreen Terrace",
    "city": "Springfield",
    "state": "OR",
    "postal_code": "97403",
    "country": "USA",
}


@pytest.fixture
def shipping():
    return dict(SHIPPING)


def image_file(name="photo.png", size=(10, 10), fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(200, 50, 50)).save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")
