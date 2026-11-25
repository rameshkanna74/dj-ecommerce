"""
Concurrency and race-condition tests for checkout, coupons and the order workflow.

The deterministic tests run on every backend. The threaded tests need real row locks and
only run on PostgreSQL:  CORECART_TEST_DB=postgresql DB_USER=... DB_PASSWORD=... uv run pytest
"""

import threading

import pytest
from django.conf import settings
from django.db import close_old_connections, connection

from cart.models import CartItem
from orders import services
from orders.models import Coupon, Order, OrderItem
from products.models import Product
from tests.conftest import make_user

SHIPPING = {
    "full_name": "Pat Buyer", "phone": "5550100", "address": "1 Main St", "city": "Springfield",
    "state": "IL", "postal_code": "62701", "country": "USA",
}

postgres_only = pytest.mark.skipif(
    settings.DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql",
    reason="needs PostgreSQL row locks (set CORECART_TEST_DB=postgresql)",
)


def checkout(user, token, coupon_code=""):
    return services.place_order(user, shipping=SHIPPING, payment_method="cod", coupon_code=coupon_code,
                                checkout_token=token)


def run_concurrently(funcs):
    """Start every callable at the same moment in its own thread (and DB connection)."""
    barrier = threading.Barrier(len(funcs))
    results = [None] * len(funcs)

    def worker(index, func):
        try:
            barrier.wait()
            results[index] = ("ok", func())
        except Exception as exc:  # noqa: BLE001 - collected and asserted by the caller
            results[index] = ("error", exc)
        finally:
            close_old_connections()
            connection.close()

    threads = [threading.Thread(target=worker, args=(i, f)) for i, f in enumerate(funcs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "a worker hung (possible deadlock)"
    return results


def unexpected(results, allowed=(services.CheckoutError,)):
    return [r[1] for r in results if r[0] == "error" and not isinstance(r[1], allowed)]


# --------------------------------------------------------------------------
# Deterministic (any backend)
# --------------------------------------------------------------------------
@pytest.mark.django_db
class TestCheckoutKeyCollisions:
    def test_key_used_by_another_user_is_a_clean_conflict_and_releases_the_coupon(
        self, customer, other_customer, product, make_coupon
    ):
        coupon = make_coupon(code="ONE", usage_limit=5)
        CartItem.objects.create(user=other_customer, product=product, quantity=1)
        checkout(other_customer, "shared-key")
        CartItem.objects.create(user=customer, product=product, quantity=2)

        with pytest.raises(services.CheckoutError, match="already used"):
            checkout(customer, "shared-key", coupon_code="ONE")

        coupon.refresh_from_db()
        product.refresh_from_db()
        assert coupon.used_count == 0  # the losing attempt's claim was rolled back
        assert product.stock == 9  # only the first order took stock
        assert CartItem.objects.filter(user=customer).count() == 1  # cart untouched
        assert Order.objects.count() == 1

    def test_customer_cancel_rechecks_rules_under_the_lock(self, customer, product, vendor):
        CartItem.objects.create(user=customer, product=product, quantity=1)
        order, _ = checkout(customer, "c1")
        stale = Order.objects.get(pk=order.pk)  # customer loaded the order while it was cancellable
        services.set_item_status(order.items.get(), OrderItem.Status.PROCESSING, vendor.user)

        with pytest.raises(services.OrderWorkflowError):
            services.cancel_order(stale, customer, by_customer=True)
        assert Order.objects.get(pk=order.pk).status == Order.Status.PROCESSING

    def test_disabled_payment_method_is_rejected(self, customer, product, settings):
        settings.CORECART_PAYMENT_METHODS = ["bank_transfer"]
        CartItem.objects.create(user=customer, product=product, quantity=1)
        with pytest.raises(services.CheckoutError, match="payment method"):
            checkout(customer, "p1")

    def test_cancel_restocks_every_line(self, customer, make_product, variant_product):
        first, second = make_product(name="A", stock=5), make_product(name="B", stock=5)
        apron, small, _ = variant_product
        CartItem.objects.create(user=customer, product=second, quantity=2)
        CartItem.objects.create(user=customer, product=apron, variant=small, quantity=1)
        CartItem.objects.create(user=customer, product=first, quantity=3)
        order, _ = checkout(customer, "r1")

        services.cancel_order(order, customer)
        first.refresh_from_db()
        second.refresh_from_db()
        small.refresh_from_db()
        assert (first.stock, second.stock, small.stock) == (5, 5, 3)


# --------------------------------------------------------------------------
# Threaded (PostgreSQL)
# --------------------------------------------------------------------------
@postgres_only
@pytest.mark.django_db(transaction=True)
class TestConcurrentCheckout:
    def test_last_units_are_never_oversold(self, make_product):
        product = make_product(stock=5)
        buyers = [make_user(f"buyer{i}") for i in range(12)]
        for buyer in buyers:
            CartItem.objects.create(user=buyer, product=product, quantity=1)

        results = run_concurrently([lambda b=b: checkout(b, f"k-{b.pk}") for b in buyers])

        assert unexpected(results) == []
        product.refresh_from_db()
        assert product.stock == 0
        assert sum(1 for r in results if r[0] == "ok") == 5
        assert OrderItem.objects.filter(product=product).count() == 5

    def test_coupon_usage_limit_holds_under_contention(self, make_product, make_coupon):
        product = make_product(stock=100)
        make_coupon(code="LIMITED", usage_limit=3)
        buyers = [make_user(f"cbuyer{i}") for i in range(10)]
        for buyer in buyers:
            CartItem.objects.create(user=buyer, product=product, quantity=1)

        results = run_concurrently([lambda b=b: checkout(b, f"c-{b.pk}", "LIMITED") for b in buyers])

        assert unexpected(results) == []
        assert Coupon.objects.get(code="LIMITED").used_count == 3
        assert Order.objects.filter(coupon_code="LIMITED").count() == 3

    def test_double_submit_creates_one_order_and_one_coupon_use(self, customer, make_product, make_coupon):
        product = make_product(stock=10)
        make_coupon(code="ONCE", usage_limit=10)
        CartItem.objects.create(user=customer, product=product, quantity=2)

        results = run_concurrently([lambda: checkout(customer, "same-key", "ONCE")] * 4)

        assert unexpected(results) == []
        assert Order.objects.count() == 1
        assert Coupon.objects.get(code="ONCE").used_count == 1
        product.refresh_from_db()
        assert product.stock == 8

    def test_overlapping_carts_do_not_deadlock(self, make_product, variant_product):
        products = [make_product(name=f"P{i}", stock=500) for i in range(4)]
        apron, small, large = variant_product
        small.stock = large.stock = 500
        small.save()
        large.save()
        buyers = [make_user(f"dbuyer{i}") for i in range(8)]
        for index, buyer in enumerate(buyers):
            # Each buyer adds the same products in a different order.
            order = products[index % 4:] + products[: index % 4]
            if index % 2:
                order.reverse()
            for product in order:
                CartItem.objects.create(user=buyer, product=product, quantity=1)
            CartItem.objects.create(user=buyer, product=apron, variant=large if index % 2 else small, quantity=1)

        results = run_concurrently([lambda b=b: checkout(b, f"d-{b.pk}") for b in buyers])

        assert [r for r in results if r[0] == "error"] == []
        assert Product.objects.get(pk=products[0].pk).stock == 500 - len(buyers)

    def test_cancels_racing_checkouts_keep_stock_consistent(self, make_product):
        first, second = make_product(name="A", stock=1000), make_product(name="B", stock=1000)
        sellers_orders = []
        for i in range(4):
            buyer = make_user(f"xbuyer{i}")
            for product in ([first, second] if i % 2 else [second, first]):
                CartItem.objects.create(user=buyer, product=product, quantity=3)
            sellers_orders.append((buyer, checkout(buyer, f"x-{i}")[0]))
        new_buyers = [make_user(f"ybuyer{i}") for i in range(4)]
        for buyer in new_buyers:
            for product in (second, first):
                CartItem.objects.create(user=buyer, product=product, quantity=2)

        jobs = [lambda b=b, o=o: services.cancel_order(o, b, by_customer=True) for b, o in sellers_orders]
        jobs += [lambda b=b: checkout(b, f"y-{b.pk}") for b in new_buyers]
        results = run_concurrently(jobs)

        assert [r for r in results if r[0] == "error"] == []
        for product in (first, second):
            product.refresh_from_db()
            assert product.stock == 1000 - 4 * 2  # all 4 cancelled orders restocked, 4 new orders taken

    def test_vendor_update_and_customer_cancel_do_not_deadlock(self, customer, vendor, make_product):
        first, second = make_product(name="A", stock=50), make_product(name="B", stock=50)
        for _ in range(5):
            CartItem.objects.create(user=customer, product=first, quantity=1)
            CartItem.objects.create(user=customer, product=second, quantity=1)
            order, _ = checkout(customer, f"v-{Order.objects.count()}")
            item = order.items.order_by("-id").first()

            results = run_concurrently([
                lambda: services.set_item_status(item, OrderItem.Status.PROCESSING, vendor.user),
                lambda: services.cancel_order(order, customer, by_customer=True),
            ])
            assert unexpected(results, allowed=(services.OrderWorkflowError,)) == []
            order.refresh_from_db()
            statuses = set(order.items.values_list("status", flat=True))
            # Exactly one side won: either everything is cancelled, or fulfilment started.
            assert statuses == {OrderItem.Status.CANCELLED} or OrderItem.Status.PROCESSING in statuses

        for product in (first, second):
            product.refresh_from_db()
        sold = OrderItem.objects.exclude(status=OrderItem.Status.CANCELLED)
        assert first.stock == 50 - sold.filter(product=first).count()
        assert second.stock == 50 - sold.filter(product=second).count()
