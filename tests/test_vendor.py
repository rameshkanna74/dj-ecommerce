from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import VendorProfile
from analytics.services import vendor_dashboard_data
from orders import payments, services
from products.models import Product, ProductVariant

from .conftest import image_file

pytestmark = pytest.mark.django_db


def product_payload(category, **overrides):
    data = {
        "category": category.pk, "name": "Copper Pot", "description": "Heavy copper pot", "price": "80.00",
        "stock": "4", "is_active": "on",
        "variants-TOTAL_FORMS": "1", "variants-INITIAL_FORMS": "0", "variants-MIN_NUM_FORMS": "0",
        "variants-MAX_NUM_FORMS": "20",
        "images-TOTAL_FORMS": "1", "images-INITIAL_FORMS": "0", "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "8",
        # Defaults a browser submits for the untouched extra rows.
        "variants-0-stock": "0", "variants-0-is_active": "on", "images-0-position": "0",
    }
    data.update(overrides)
    return data


class TestApprovalWorkflow:
    def test_admin_action_approves_and_notifies(self, login, admin_user, pending_vendor, mailoutbox):
        client = login(admin_user)
        response = client.post(
            reverse("admin:accounts_vendorprofile_changelist"),
            {"action": "approve_vendors", "_selected_action": [pending_vendor.pk]},
        )
        assert response.status_code == 302
        pending_vendor.refresh_from_db()
        assert pending_vendor.is_approved and pending_vendor.approved_by == admin_user
        assert "Approved" in mailoutbox[0].subject

    def test_reject_action(self, login, admin_user, pending_vendor):
        login(admin_user).post(
            reverse("admin:accounts_vendorprofile_changelist"),
            {"action": "reject_vendors", "_selected_action": [pending_vendor.pk]},
        )
        pending_vendor.refresh_from_db()
        assert pending_vendor.approval_status == VendorProfile.Approval.REJECTED

    def test_rejected_vendor_cannot_publish(self, login, pending_vendor, category):
        pending_vendor.reject()
        client = login(pending_vendor.user)
        response = client.post(reverse("products:create"), product_payload(category))
        assert response.status_code == 302 and response.url == reverse("accounts:vendor_pending")
        assert not Product.objects.exists()

    def test_suspension_hides_products(self, client, vendor, product):
        assert client.get(product.get_absolute_url()).status_code == 200
        vendor.suspend(reason="Policy violation")
        assert client.get(product.get_absolute_url()).status_code == 404


class TestProductManagement:
    def test_create_product_assigns_owner_server_side(self, vendor_client, vendor, other_vendor, category):
        response = vendor_client.post(
            reverse("products:create"),
            product_payload(category, vendor=other_vendor.pk, **{"variants-0-attribute_name": "",
                                                                 "cover_image": image_file()}),
        )
        assert response.status_code == 302
        product = Product.objects.get()
        assert product.vendor == vendor and product.slug == "copper-pot"
        assert product.cover_image.name.startswith("products/")

    def test_create_with_variant_and_gallery_image(self, vendor_client, category):
        payload = product_payload(
            category,
            **{
                "variants-0-attribute_name": "Size", "variants-0-attribute_value": "XL", "variants-0-stock": "7",
                "variants-0-price_override": "90.00", "variants-0-is_active": "on",
                "images-0-image": image_file("g.png"), "images-0-alt_text": "Side", "images-0-position": "1",
            },
        )
        assert vendor_client.post(reverse("products:create"), payload).status_code == 302
        product = Product.objects.get()
        assert product.variants.get().price_override == Decimal("90.00")
        assert product.images.count() == 1

    def test_invalid_product_shows_errors(self, vendor_client, category):
        response = vendor_client.post(reverse("products:create"), product_payload(category, price="-5", name=""))
        assert response.status_code == 200
        assert not Product.objects.exists()
        assert "Please correct the highlighted fields" in response.content.decode()

    def test_vendor_cannot_edit_or_delete_other_vendor_products(self, login, other_vendor, product, category):
        client = login(other_vendor.user)
        assert client.get(reverse("products:update", args=[product.pk])).status_code == 404
        assert client.post(reverse("products:update", args=[product.pk]), product_payload(category)).status_code == 404
        assert client.post(reverse("products:delete", args=[product.pk])).status_code == 404
        assert client.post(reverse("products:update_stock", args=[product.pk]), {"stock": 0}).status_code == 404
        product.refresh_from_db()
        assert product.name == "Chef Knife" and product.stock == 10

    def test_vendor_list_only_shows_own(self, login, vendor, make_product, other_vendor):
        make_product(name="Mine")
        make_product(name="Theirs", owner=other_vendor)
        names = [p.name for p in login(vendor.user).get(reverse("products:vendor_list")).context["products"]]
        assert names == ["Mine"]

    def test_update_stock_and_variant_stock(self, vendor_client, product, variant_product):
        vendor_client.post(reverse("products:update_stock", args=[product.pk]), {"stock": 42})
        product.refresh_from_db()
        assert product.stock == 42
        apron, small, _ = variant_product
        vendor_client.post(reverse("products:update_stock", args=[apron.pk]), {"stock": 9, "variant": small.pk})
        small.refresh_from_db()
        assert small.stock == 9
        vendor_client.post(reverse("products:update_stock", args=[product.pk]), {"stock": -1})
        product.refresh_from_db()
        assert product.stock == 42

    def test_variant_from_other_product_cannot_be_updated(self, vendor_client, product, variant_product):
        _, small, _ = variant_product
        response = vendor_client.post(reverse("products:update_stock", args=[product.pk]),
                                      {"stock": 1, "variant": small.pk})
        assert response.status_code == 404

    def test_delete_product_with_orders_hides_it(self, vendor_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="d")
        vendor_client.post(reverse("products:delete", args=[product.pk]))
        product.refresh_from_db()
        assert not product.is_active

    def test_delete_product_without_orders(self, vendor_client, product):
        vendor_client.post(reverse("products:delete", args=[product.pk]))
        assert not Product.objects.exists()


class TestVendorAnalytics:
    def test_dashboard_numbers_reflect_real_orders(self, vendor, other_vendor, customer, make_product, fill_cart,
                                                   shipping, admin_user):
        mine = make_product(name="Mine", price="50.00", stock=20)
        theirs = make_product(name="Theirs", price="7.00", stock=20, owner=other_vendor)
        make_product(name="Idle", is_active=False)

        fill_cart(customer, mine, 2)
        fill_cart(customer, theirs, 1)
        paid, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="a")
        payments.mark_order_paid(paid, admin_user)

        fill_cart(customer, mine, 1)
        unpaid, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="b")

        fill_cart(customer, mine, 3)
        cancelled, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="c")
        services.cancel_order(cancelled, customer)

        kpis = vendor_dashboard_data(vendor)["kpis"]
        assert kpis["total_products"] == 2 and kpis["active_products"] == 1
        assert kpis["total_orders"] == 3
        assert kpis["pending_orders"] == 2
        assert kpis["units_sold"] == 3
        assert kpis["gross_sales"] == Decimal("150.00")
        assert kpis["recognised_sales"] == Decimal("100.00")
        assert kpis["revenue"] == Decimal("90.00")  # 10% commission

        other = vendor_dashboard_data(other_vendor)["kpis"]
        assert other["gross_sales"] == Decimal("7.00") and other["units_sold"] == 1

    def test_dashboard_pages_render(self, vendor_client):
        assert vendor_client.get(reverse("accounts:vendor_dashboard")).status_code == 200
        response = vendor_client.get(reverse("analytics:vendor_dashboard"), {"days": 7})
        assert response.status_code == 200 and response.context["days"] == 7

    def test_vendor_csv_export_contains_only_own_sales(self, vendor_client, customer, product, make_product,
                                                       other_vendor, fill_cart, shipping):
        fill_cart(customer, product)
        fill_cart(customer, make_product(name="Foreign", owner=other_vendor))
        services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="e")
        response = vendor_client.get(reverse("analytics:vendor_export_sales"))
        body = response.content.decode()
        assert response["Content-Type"].startswith("text/csv")
        assert "Chef Knife" in body and "Foreign" not in body


def test_variant_product_listing_price(variant_product):
    product, small, large = variant_product
    assert product.has_variants and product.total_available_stock == 5
    assert ProductVariant.objects.get(pk=small.pk).current_price == Decimal("30.00")
