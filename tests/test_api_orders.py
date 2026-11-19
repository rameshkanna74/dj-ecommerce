from decimal import Decimal

import pytest
from django.urls import reverse

from cart.models import CartItem
from orders.models import Coupon, Order
from products.models import Product

pytestmark = pytest.mark.django_db


def checkout(client, shipping, key="key-1", **extra):
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    return client.post(reverse("api:checkout"), {**shipping, "payment_method": "cod", **extra}, format="json",
                       **headers)


class TestCart:
    def test_add_update_save_remove(self, api, customer, product):
        client = api(customer)
        body = client.post(reverse("api:cart-items"), {"product": product.pk, "quantity": 2}, format="json").json()
        assert body["subtotal"] == "50.00" and body["total_quantity"] == 2
        item_id = body["items"][0]["id"]
        url = reverse("api:cart-item", args=[item_id])
        assert client.patch(url, {"quantity": 3}, format="json").json()["subtotal"] == "75.00"
        saved = client.patch(url, {"is_saved_for_later": True}, format="json").json()
        assert saved["items"] == [] and saved["saved_items"][0]["id"] == item_id
        assert client.delete(url).json()["saved_items"] == []

    def test_business_rule_errors(self, api, customer, make_product):
        product = make_product(stock=2)
        response = api(customer).post(reverse("api:cart-items"), {"product": product.pk, "quantity": 5},
                                      format="json")
        assert response.status_code == 400
        assert response.json() == {"detail": "Only 2 left in stock.", "code": "cart_error"}

    def test_variant_required(self, api, customer, variant_product):
        product, small, _ = variant_product
        client = api(customer)
        assert client.post(reverse("api:cart-items"), {"product": product.pk}, format="json").status_code == 400
        assert client.post(reverse("api:cart-items"), {"product": product.pk, "variant": small.pk},
                           format="json").status_code == 201

    def test_cannot_touch_other_users_items(self, api, customer, other_customer, product, fill_cart):
        item = fill_cart(customer, product)
        url = reverse("api:cart-item", args=[item.pk])
        assert api(other_customer).patch(url, {"quantity": 5}, format="json").status_code == 404
        assert api(other_customer).delete(url).status_code == 404

    def test_vendor_and_anonymous_blocked(self, api, vendor):
        assert api(vendor.user).get(reverse("api:cart")).status_code == 403
        assert api().get(reverse("api:cart")).status_code == 401


class TestCheckout:
    def test_preview(self, api, customer, product, fill_cart, make_coupon):
        fill_cart(customer, product, 2)
        make_coupon(code="SAVE10")
        body = api(customer).post(reverse("api:checkout-preview"), {"coupon_code": "save10"}, format="json").json()
        assert (body["subtotal"], body["discount"], body["total"], body["coupon_code"]) == (
            "50.00", "5.00", "45.00", "SAVE10")
        bad = api(customer).post(reverse("api:checkout-preview"), {"coupon_code": "nope"}, format="json").json()
        assert bad["coupon_error"] == "Invalid coupon code." and bad["discount"] == "0.00"

    def test_place_order_and_idempotent_retry(self, api, customer, product, fill_cart, shipping, make_coupon):
        fill_cart(customer, product, 2)
        make_coupon(code="SAVE10")
        client = api(customer)
        first = checkout(client, shipping, coupon_code="SAVE10", save_address=True)
        assert first.status_code == 201
        order = first.json()
        assert order["total_amount"] == "45.00" and order["payment_status"] == "unpaid"
        assert order["items"][0]["price"] == "25.00" and order["shipping_address"]["city"] == "Springfield"
        retry = checkout(client, shipping, coupon_code="SAVE10")
        assert retry.status_code == 200 and retry.json()["order_number"] == order["order_number"]
        assert Order.objects.count() == 1 and Coupon.objects.get().used_count == 1
        product.refresh_from_db()
        assert product.stock == 8
        customer.customer_profile.refresh_from_db()
        assert customer.customer_profile.city == "Springfield"

    def test_idempotency_key_required_and_not_shareable(self, api, customer, other_customer, product, fill_cart,
                                                        shipping):
        fill_cart(customer, product)
        assert checkout(api(customer), shipping, key=None).json()["code"] == "idempotency_key_required"
        checkout(api(customer), shipping, key="shared")
        fill_cart(other_customer, product)
        assert checkout(api(other_customer), shipping, key="shared").status_code == 409

    def test_inventory_conflict_rolls_back(self, api, customer, make_product, fill_cart, shipping):
        product = make_product(stock=5)
        fill_cart(customer, product, 4)
        Product.objects.filter(pk=product.pk).update(stock=3)
        response = checkout(api(customer), shipping)
        assert response.status_code == 409 and response.json()["code"] == "checkout_conflict"
        assert not Order.objects.exists() and CartItem.objects.count() == 1

    def test_browser_supplied_totals_ignored_and_validation(self, api, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        bad = checkout(api(customer), {**shipping, "phone": "x"}, key="a")
        assert bad.status_code == 400 and "phone" in bad.json()
        ok = checkout(api(customer), shipping, key="b", total_amount="0.01", payment_status="paid")
        assert ok.json()["total_amount"] == "25.00" and ok.json()["payment_status"] == "unpaid"

    def test_empty_cart(self, api, customer, shipping):
        assert checkout(api(customer), shipping).status_code == 409

    def test_payment_methods(self, api, customer):
        values = [m["value"] for m in api(customer).get(reverse("api:payment-methods")).json()]
        assert values == ["cod", "bank_transfer"]


class TestCustomerOrders:
    @pytest.fixture
    def order(self, api, customer, product, fill_cart, shipping):
        fill_cart(customer, product, 2)
        return checkout(api(customer), shipping).json()

    def test_list_detail_ownership(self, api, customer, other_customer, order):
        assert api(customer).get(reverse("api:orders")).json()["results"][0]["item_count"] == 1
        url = reverse("api:order-detail", args=[order["order_number"]])
        assert api(customer).get(url).json()["can_cancel"] is True
        assert api(other_customer).get(url).status_code == 404
        assert api(other_customer).get(reverse("api:orders")).json()["count"] == 0

    def test_cancel(self, api, customer, other_customer, product, order):
        url = reverse("api:order-cancel", args=[order["order_number"]])
        assert api(other_customer).post(url).status_code == 404
        body = api(customer).post(url, {"reason": "Changed my mind"}, format="json").json()
        assert body["status"] == "cancelled" and body["can_cancel"] is False
        product.refresh_from_db()
        assert product.stock == 10
        assert api(customer).post(url).status_code == 409


def test_order_totals_decimal_strings(api, customer, make_product, fill_cart, shipping):
    fill_cart(customer, make_product(price="0.10"), 3)
    assert checkout(api(customer), shipping).json()["total_amount"] == "0.30"
    assert Order.objects.get().total_amount == Decimal("0.30")
