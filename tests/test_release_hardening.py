"""Regression tests for issues fixed while hardening the 1.0 release."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import CustomUser
from orders import payments, services
from orders.models import OrderItem
from products.forms import ProductVariantFormSet
from products.models import ProductVariant, Review

from .conftest import PASSWORD, make_user

pytestmark = pytest.mark.django_db


def order_from(customer, items, shipping, token):
    """``items``: list of (product, quantity, variant)."""
    from cart.models import CartItem

    for product, quantity, variant in items:
        CartItem.objects.create(user=customer, product=product, quantity=quantity, variant=variant)
    order, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token=token)
    return order


class TestVariantsWithOrders:
    def test_api_refuses_to_delete_a_sold_variant(self, api, vendor, customer, variant_product, shipping):
        product, small, _ = variant_product
        order_from(customer, [(product, 1, small)], shipping, "v1")
        url = reverse("api:vendor-variant-detail", args=[product.pk, small.pk])
        response = api(vendor.user).delete(url)
        assert response.status_code == 409
        assert ProductVariant.objects.filter(pk=small.pk).exists()
        assert api(vendor.user).patch(url, {"is_active": False}, format="json").status_code == 200

    def test_unsold_variant_can_still_be_deleted(self, api, vendor, variant_product):
        product, _, large = variant_product
        assert api(vendor.user).delete(
            reverse("api:vendor-variant-detail", args=[product.pk, large.pk])).status_code == 204

    def test_formset_refuses_to_delete_a_sold_variant(self, customer, variant_product, shipping):
        product, small, large = variant_product
        order_from(customer, [(product, 1, small)], shipping, "v2")
        data = {"variants-TOTAL_FORMS": "2", "variants-INITIAL_FORMS": "2", "variants-MIN_NUM_FORMS": "0",
                "variants-MAX_NUM_FORMS": "20"}
        for i, v in enumerate([small, large]):
            data.update({f"variants-{i}-id": str(v.pk), f"variants-{i}-attribute_name": v.attribute_name,
                         f"variants-{i}-attribute_value": v.attribute_value, f"variants-{i}-stock": str(v.stock),
                         f"variants-{i}-is_active": "on"})
        data["variants-0-DELETE"] = "on"
        formset = ProductVariantFormSet(data, instance=product, prefix="variants")
        assert not formset.is_valid()
        assert "cannot be deleted" in str(formset.non_form_errors())

    def test_cancel_restocks_the_variant_not_the_product(self, customer, variant_product, shipping):
        product, small, _ = variant_product
        order = order_from(customer, [(product, 2, small)], shipping, "v3")
        services.cancel_order(order, customer)
        small.refresh_from_db()
        product.refresh_from_db()
        assert (small.stock, product.stock) == (3, 0)


class TestStockKpis:
    def test_products_with_variant_stock_are_not_reported_out_of_stock(self, api, admin_user, vendor,
                                                                        variant_product, make_product):
        make_product(name="Empty", stock=0)
        body = api(admin_user).get(reverse("api:staff-dashboard")).json()
        assert body["kpis"]["out_of_stock"] == 1  # only "Empty"; the apron has 5 units across variants
        vendor_body = api(vendor.user).get(reverse("api:vendor-dashboard")).json()
        assert vendor_body["kpis"]["out_of_stock"] == 1

    def test_low_stock_filter_uses_variant_stock(self, api, admin_user, variant_product, make_product):
        product, small, large = variant_product
        make_product(name="Plenty", stock=50)
        names = [p["name"] for p in api(admin_user).get(reverse("api:staff-product-list"),
                                                         {"low_stock": "1"}).json()["results"]]
        assert names == ["Linen Apron"]  # 5 units in total
        small.stock, large.stock = 40, 40
        small.save()
        large.save()
        assert api(admin_user).get(reverse("api:staff-product-list"), {"low_stock": "1"}).json()["results"] == []


class TestVendorNetRevenue:
    def test_net_is_the_sum_of_per_line_rounded_earnings(self, api, vendor, admin_user, customer, other_customer,
                                                         make_product, shipping):
        product = make_product(price="10.05", stock=10)  # vendor commission is 10%
        paid = [order_from(user, [(product, 1, None)], shipping, f"n{i}")
                for i, user in enumerate([customer, other_customer])]
        for order in paid:
            payments.mark_order_paid(order, admin_user)
        expected = sum(item.vendor_earnings for item in OrderItem.objects.filter(vendor=vendor))
        assert expected == Decimal("18.08")
        body = api(vendor.user).get(reverse("api:vendor-dashboard")).json()
        assert body["kpis"]["revenue"] == "18.08"


class TestStaffGuards:
    def test_staff_cannot_rewrite_a_review_rating(self, api, admin_user, customer, product):
        review = Review.objects.create(product=product, user=customer, rating=5, comment="Great")
        response = api(admin_user).patch(reverse("api:staff-review-detail", args=[review.pk]),
                                         {"rating": 1, "is_visible": False}, format="json")
        assert response.status_code == 200
        review.refresh_from_db()
        assert (review.rating, review.is_visible) == (5, False)

    def test_platform_admin_cannot_deactivate_a_superuser(self, api, admin_user):
        staff_admin = make_user("ops", role=CustomUser.Role.ADMIN, is_staff=True)
        response = api(staff_admin).patch(reverse("api:staff-user-detail", args=[admin_user.pk]),
                                          {"is_active": False}, format="json")
        assert response.status_code == 403
        admin_user.refresh_from_db()
        assert admin_user.is_active

    def test_superuser_can_still_manage_platform_admins(self, api, admin_user):
        staff_admin = make_user("ops", role=CustomUser.Role.ADMIN, is_staff=True)
        response = api(admin_user).patch(reverse("api:staff-user-detail", args=[staff_admin.pk]),
                                         {"is_active": False}, format="json")
        assert response.status_code == 200


class TestAccountHardening:
    def test_username_containing_at_sign_can_log_in(self):
        make_user("joe@corp")
        response = APIClient().post(reverse("api:token"), {"username": "joe@corp", "password": PASSWORD},
                                    format="json")
        assert response.status_code == 200

    def test_email_login_still_works(self, customer):
        response = APIClient().post(reverse("api:token"), {"username": customer.email.upper(),
                                                           "password": PASSWORD}, format="json")
        assert response.status_code == 200

    def test_changing_email_requires_current_password(self, api, customer):
        client = api(customer)
        url = reverse("api:me")
        assert client.patch(url, {"email": "new@example.com"}, format="json").status_code == 400
        assert client.patch(url, {"email": "new@example.com", "current_password": "wrong"},
                            format="json").status_code == 400
        assert client.patch(url, {"email": "new@example.com", "current_password": PASSWORD},
                            format="json").status_code == 200
        customer.refresh_from_db()
        assert customer.email == "new@example.com"

    def test_other_profile_fields_need_no_password(self, api, customer):
        response = api(customer).patch(reverse("api:me"), {"first_name": "Al", "email": customer.email},
                                       format="json")
        assert response.status_code == 200

    def test_site_login_is_rate_limited(self, client, customer):
        url = reverse("accounts:login")
        codes = [client.post(url, {"username": "alice", "password": "wrong"}, REMOTE_ADDR="198.51.100.9",
                             HTTP_X_FORWARDED_FOR=f"10.1.0.{i}").status_code for i in range(25)]
        assert codes[0] == 200 and codes[-1] == 429
        # Blocked even with the right password until the window passes.
        assert client.post(url, {"username": "alice", "password": PASSWORD},
                           REMOTE_ADDR="198.51.100.9").status_code == 429
        # Another client is unaffected.
        assert client.post(url, {"username": "alice", "password": PASSWORD},
                           REMOTE_ADDR="198.51.100.10").status_code == 302

    def test_site_password_reset_is_rate_limited(self, client, customer):
        url = reverse("accounts:password_reset")
        codes = [client.post(url, {"email": customer.email}).status_code for _ in range(12)]
        assert codes[0] == 302 and codes[-1] == 429
