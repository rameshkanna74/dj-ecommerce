"""Create demo data for local development: categories, a vendor, products and a coupon."""

import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser, VendorProfile
from orders.models import Coupon
from products.models import Category, Product, ProductVariant

CATALOGUE = {
    "Kitchen": [("Carbon Steel Chef Knife", "89.00", 14), ("Walnut Cutting Board", "54.00", 8),
                ("Enamel Dutch Oven", "129.00", 3)],
    "Home": [("Linen Throw Blanket", "75.00", 11), ("Stoneware Vase", "38.00", 0), ("Beeswax Candle Set", "24.00", 30)],
    "Apparel": [("Organic Cotton Tee", "29.00", 0)],
}


class Command(BaseCommand):
    help = "Seed demo marketplace data (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Allow running when DEBUG is off.")

    @transaction.atomic
    def handle(self, *args, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError("Refusing to seed demo data with DEBUG off. Use --force if you really mean it.")

        password = secrets.token_urlsafe(9)
        vendor_user, created = CustomUser.objects.get_or_create(
            username="demo_vendor",
            defaults={"email": "demo_vendor@example.com", "role": CustomUser.Role.VENDOR, "first_name": "Demo"},
        )
        customer, customer_created = CustomUser.objects.get_or_create(
            username="demo_customer",
            defaults={"email": "demo_customer@example.com", "first_name": "Dana", "last_name": "Demo"},
        )
        for user, is_new in ((vendor_user, created), (customer, customer_created)):
            if is_new:
                user.set_password(password)
                user.save()

        vendor, _ = VendorProfile.objects.get_or_create(
            user=vendor_user,
            defaults={
                "business_name": "Hearth & Field", "business_description": "Small-batch goods for everyday living.",
                "business_email": "studio@example.com", "business_phone": "555-0100", "business_address": "1 Mill Lane",
                "business_city": "Portland", "business_state": "OR", "business_zip_code": "97201",
                "store_slug": "hearth-and-field",
            },
        )
        if not vendor.is_approved:
            vendor.approve()

        for category_name, items in CATALOGUE.items():
            category, _ = Category.objects.get_or_create(name=category_name)
            for index, (name, price, stock) in enumerate(items):
                product, made = Product.objects.get_or_create(
                    name=name,
                    defaults={"category": category, "vendor": vendor, "price": Decimal(price), "stock": stock,
                              "description": f"{name}, made in small batches by Hearth & Field.",
                              "is_featured": index == 0},
                )
                if made and name == "Organic Cotton Tee":
                    for size, qty in (("S", 4), ("M", 6), ("L", 0)):
                        ProductVariant.objects.create(product=product, attribute_name="Size", attribute_value=size,
                                                      stock=qty)

        Coupon.objects.get_or_create(
            code="WELCOME10",
            defaults={"discount_type": "percentage", "value": Decimal("10"), "description": "10% off your order",
                      "valid_from": timezone.now() - timedelta(days=1),
                      "valid_to": timezone.now() + timedelta(days=365), "usage_limit": 1000},
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready. Coupon: WELCOME10"))
        if created or customer_created:
            self.stdout.write(f"Accounts demo_vendor / demo_customer, password: {password}")
        else:
            self.stdout.write("Demo accounts already existed; their passwords were not changed.")
