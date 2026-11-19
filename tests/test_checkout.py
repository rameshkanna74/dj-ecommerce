from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from cart.models import CartItem
from orders import services
from orders.models import Coupon, CouponError, Order, OrderItem
from products.models import Product

pytestmark = pytest.mark.django_db


def checkout_get(client):
    return client.get(reverse("orders:checkout"))


def checkout_post(client, shipping, token=None, **extra):
    if token is None:
        token = client.session.get("checkout_token") or checkout_get(client).context["form"].initial["checkout_token"]
    data = {**shipping, "payment_method": "cod", "checkout_token": token, **extra}
    return client.post(reverse("orders:checkout"), data)


class TestCouponModel:
    def test_percentage_and_fixed_discounts(self, make_coupon):
        assert make_coupon(value="10").calculate_discount(Decimal("80.00")) == Decimal("8.00")
        assert make_coupon(code="F5", discount_type="fixed", value="5").calculate_discount(Decimal("80")) == Decimal("5.00")

    def test_discount_never_exceeds_subtotal(self, make_coupon):
        assert make_coupon(code="BIG", discount_type="fixed", value="500").calculate_discount(Decimal("20")) == Decimal("20.00")

    def test_rounding(self, make_coupon):
        assert make_coupon(code="R", value="15").calculate_discount(Decimal("9.99")) == Decimal("1.50")

    @pytest.mark.parametrize(
        "overrides,message",
        [
            ({"active": False}, "not active"),
            ({"valid_from": timezone.now() + timedelta(days=1), "valid_to": timezone.now() + timedelta(days=2)},
             "not valid yet"),
            ({"valid_from": timezone.now() - timedelta(days=5), "valid_to": timezone.now() - timedelta(days=1)},
             "expired"),
            ({"usage_limit": 1, "used_count": 1}, "usage limit"),
            ({"min_order_amount": Decimal("100")}, "minimum order"),
        ],
    )
    def test_validation_rules(self, make_coupon, overrides, message):
        coupon = make_coupon(**overrides)
        with pytest.raises(CouponError, match=message):
            coupon.validate_for(Decimal("50"))

    def test_code_normalised_to_upper_case(self, make_coupon):
        assert make_coupon(code=" welcome ").code == "WELCOME"


class TestCheckoutPage:
    def test_empty_cart_redirects(self, customer_client):
        response = checkout_get(customer_client)
        assert response.status_code == 302 and response.url == reverse("cart:view")

    def test_only_saved_items_counts_as_empty(self, customer_client, customer, product, fill_cart):
        fill_cart(customer, product, saved=True)
        assert checkout_get(customer_client).status_code == 302

    def test_page_prefills_address_from_profile(self, customer_client, customer, product, fill_cart):
        profile = customer.customer_profile
        profile.address, profile.city = "1 Elm St", "Portland"
        profile.save()
        fill_cart(customer, product)
        form = checkout_get(customer_client).context["form"]
        assert form.initial["address"] == "1 Elm St" and form.initial["city"] == "Portland"

    def test_apply_invalid_and_expired_coupon(self, customer_client, customer, product, fill_cart, make_coupon):
        fill_cart(customer, product)
        make_coupon(code="OLD", valid_from=timezone.now() - timedelta(days=9), valid_to=timezone.now() - timedelta(days=1))
        response = customer_client.post(reverse("orders:apply_coupon"), {"code": "nope"}, follow=True)
        assert "Invalid coupon code" in response.content.decode()
        response = customer_client.post(reverse("orders:apply_coupon"), {"code": "old"}, follow=True)
        assert "expired" in response.content.decode()
        assert "checkout_coupon" not in customer_client.session

    def test_apply_valid_coupon_shows_discount(self, customer_client, customer, product, fill_cart, make_coupon):
        fill_cart(customer, product, 2)  # 50.00
        make_coupon(code="SAVE10")
        customer_client.post(reverse("orders:apply_coupon"), {"code": "save10"})
        summary = checkout_get(customer_client).context["summary"]
        assert summary.discount == Decimal("5.00") and summary.total == Decimal("45.00")


class TestPlaceOrder:
    def test_valid_order_totals_snapshots_stock_and_cart(
        self, customer_client, customer, make_product, fill_cart, shipping, make_coupon, vendor
    ):
        knife = make_product(name="Knife", price="25.00", stock=10)
        board = make_product(name="Board", price="12.50", stock=4, owner=None)
        saved = make_product(name="Saved", price="99.00", stock=5)
        fill_cart(customer, knife, 2)
        fill_cart(customer, board, 3)
        fill_cart(customer, saved, 1, saved=True)
        make_coupon(code="SAVE10")
        customer_client.post(reverse("orders:apply_coupon"), {"code": "SAVE10"})

        response = checkout_post(customer_client, shipping)
        order = Order.objects.get()
        assert response.status_code == 302 and response.url == order.get_absolute_url()

        assert order.subtotal_amount == Decimal("87.50")
        assert order.discount_amount == Decimal("8.75")
        assert order.total_amount == Decimal("78.75")
        assert order.coupon_code == "SAVE10"
        assert order.status == "pending" and order.payment_status == "unpaid"
        assert order.shipping_city == "Springfield" and order.shipping_full_name == "Alice Smith"
        assert order.order_number.startswith("CC")

        items = {i.product_name: i for i in order.items.all()}
        assert set(items) == {"Knife", "Board"}
        assert items["Knife"].price == Decimal("25.00") and items["Knife"].vendor == vendor
        assert items["Knife"].commission_rate == Decimal("10.00")
        assert items["Board"].vendor is None and items["Board"].commission_rate == 0

        knife.refresh_from_db()
        board.refresh_from_db()
        assert knife.stock == 8 and board.stock == 1
        assert Coupon.objects.get().used_count == 1
        assert list(CartItem.objects.filter(user=customer)) == [CartItem.objects.get(product=saved)]
        assert order.timeline.count() == 1

    def test_order_is_never_paid_on_creation(self, customer_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        checkout_post(customer_client, shipping, payment_method="bank_transfer")
        order = Order.objects.get()
        assert order.payment_status == "unpaid" and order.paid_at is None
        assert order.payment_method == "bank_transfer"

    def test_price_snapshot_is_immutable(self, customer_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        checkout_post(customer_client, shipping)
        product.price = Decimal("999.00")
        product.save()
        item = OrderItem.objects.get()
        assert item.price == Decimal("25.00") and item.order.total_amount == Decimal("25.00")

    def test_browser_cannot_set_prices_or_totals(self, customer_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        checkout_post(customer_client, shipping, total_amount="0.01", price="0.01", discount_amount="25")
        assert Order.objects.get().total_amount == Decimal("25.00")

    def test_inventory_conflict_rolls_back(self, customer_client, customer, make_product, fill_cart, shipping,
                                           make_coupon):
        product = make_product(stock=5)
        fill_cart(customer, product, 4)
        make_coupon(code="SAVE10")
        customer_client.post(reverse("orders:apply_coupon"), {"code": "SAVE10"})
        token = checkout_get(customer_client).context["form"].initial["checkout_token"]
        Product.objects.filter(pk=product.pk).update(stock=3)  # someone else bought some

        response = checkout_post(customer_client, shipping, token=token)
        assert response.status_code == 302 and response.url == reverse("cart:view")
        assert not Order.objects.exists()
        product.refresh_from_db()
        assert product.stock == 3
        assert Coupon.objects.get().used_count == 0
        assert CartItem.objects.filter(user=customer).count() == 1

    def test_rollback_after_mid_transaction_failure(self, customer, make_product, fill_cart, shipping, make_coupon,
                                                    monkeypatch):
        a = make_product(name="A", stock=5)
        b = make_product(name="B", stock=5)
        fill_cart(customer, a, 2)
        fill_cart(customer, b, 2)
        make_coupon(code="SAVE10")

        def boom(*args, **kwargs):
            raise RuntimeError("database went away")

        monkeypatch.setattr(OrderItem.objects, "bulk_create", boom)
        with pytest.raises(RuntimeError):
            services.place_order(customer, shipping=shipping, payment_method="cod", coupon_code="SAVE10",
                                 checkout_token="tok-1")
        a.refresh_from_db()
        b.refresh_from_db()
        assert (a.stock, b.stock) == (5, 5)
        assert not Order.objects.exists()
        assert Coupon.objects.get().used_count == 0
        assert CartItem.objects.filter(user=customer).count() == 2

    def test_inactive_product_in_cart_blocks_checkout(self, customer, make_product, fill_cart, shipping):
        product = make_product()
        fill_cart(customer, product)
        product.is_active = False
        product.save()
        with pytest.raises(services.CheckoutError, match="no longer available"):
            services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="t")

    def test_unapproved_vendor_product_blocks_checkout(self, customer, product, vendor, fill_cart, shipping):
        fill_cart(customer, product)
        vendor.suspend()
        with pytest.raises(services.CheckoutError):
            services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="t")

    def test_duplicate_submission_creates_one_order(self, customer_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product, 2)
        token = checkout_get(customer_client).context["form"].initial["checkout_token"]
        first = checkout_post(customer_client, shipping, token=token)
        second = checkout_post(customer_client, shipping, token=token)
        assert Order.objects.count() == 1
        assert second.status_code == 302 and second.url == first.url
        product.refresh_from_db()
        assert product.stock == 8

    def test_service_is_idempotent_per_token(self, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        order, created = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="x")
        again, created_again = services.place_order(customer, shipping=shipping, payment_method="cod",
                                                    checkout_token="x")
        assert created and not created_again and again == order

    def test_stale_token_is_rejected(self, customer_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        checkout_get(customer_client)
        response = checkout_post(customer_client, shipping, token="forged-token")
        assert response.status_code == 302 and response.url == reverse("orders:checkout")
        assert not Order.objects.exists()

    def test_invalid_delivery_details(self, customer_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        response = checkout_post(customer_client, {**shipping, "phone": "abc", "city": ""})
        assert response.status_code == 200
        assert "Enter a valid phone number" in response.content.decode()
        assert not Order.objects.exists()

    def test_invalid_payment_method(self, customer_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        checkout_post(customer_client, shipping, payment_method="free_money")
        assert not Order.objects.exists()

    def test_coupon_usage_limit_enforced_at_checkout(self, customer, product, fill_cart, shipping, make_coupon):
        make_coupon(code="ONCE", usage_limit=1, used_count=1)
        fill_cart(customer, product)
        with pytest.raises(services.CheckoutError, match="usage limit"):
            services.place_order(customer, shipping=shipping, payment_method="cod", coupon_code="ONCE",
                                 checkout_token="t")

    def test_variant_checkout_uses_variant_price_and_stock(self, customer, variant_product, fill_cart, shipping):
        product, small, large = variant_product
        fill_cart(customer, product, 2, variant=large)
        order, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="v")
        item = order.items.get()
        assert item.price == Decimal("35.00") and item.variant_label == "Size: L"
        large.refresh_from_db()
        assert large.stock == 0 and order.total_amount == Decimal("70.00")

    def test_saves_default_address(self, customer_client, customer, product, fill_cart, shipping):
        fill_cart(customer, product)
        checkout_post(customer_client, shipping, save_address="on")
        customer.customer_profile.refresh_from_db()
        assert customer.customer_profile.city == "Springfield"

    def test_confirmation_emails(self, customer, product, fill_cart, shipping, mailoutbox,
                                 django_capture_on_commit_callbacks):
        fill_cart(customer, product)
        with django_capture_on_commit_callbacks(execute=True):
            order, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="m")
        subjects = [m.subject for m in mailoutbox]
        assert f"Order {order.order_number} confirmed" in subjects
        assert any(s.startswith("New order") for s in subjects)
