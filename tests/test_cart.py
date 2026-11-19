from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.urls import reverse

from cart import services
from cart.models import CartItem

pytestmark = pytest.mark.django_db


def add(client, product, quantity=1, variant=None):
    data = {"quantity": quantity}
    if variant:
        data["variant"] = variant.pk
    return client.post(reverse("cart:add", args=[product.pk]), data)


class TestAdd:
    def test_add_and_duplicate_add_merges(self, customer_client, customer, product):
        add(customer_client, product, 2)
        add(customer_client, product, 3)
        item = CartItem.objects.get(user=customer)
        assert item.quantity == 5

    def test_get_is_not_allowed(self, customer_client, product):
        assert customer_client.get(reverse("cart:add", args=[product.pk])).status_code == 405

    @pytest.mark.parametrize("quantity", [0, -2, "abc"])
    def test_invalid_quantities_rejected(self, customer_client, customer, product, quantity):
        add(customer_client, product, quantity)
        assert not CartItem.objects.filter(user=customer).exists()

    def test_cannot_exceed_stock(self, customer_client, customer, make_product):
        product = make_product(stock=2)
        response = add(customer_client, product, 3)
        assert not CartItem.objects.filter(user=customer).exists()
        follow = customer_client.get(response.url)
        assert "Only 2 left" in follow.content.decode()

    def test_inactive_product_cannot_be_added(self, customer_client, customer, make_product):
        product = make_product(is_active=False)
        assert add(customer_client, product).status_code == 404

    def test_variant_required_and_scoped(self, customer_client, customer, variant_product, make_product):
        product, small, large = variant_product
        add(customer_client, product)
        assert not CartItem.objects.exists()
        foreign = make_product(name="Other")
        assert add(customer_client, foreign, 1, variant=small).status_code == 404
        add(customer_client, product, 2, variant=large)
        item = CartItem.objects.get()
        assert item.variant == large and item.unit_price == Decimal("35.00")

    def test_variant_stock_enforced(self, customer_client, variant_product):
        product, small, large = variant_product
        add(customer_client, product, 3, variant=large)
        assert not CartItem.objects.exists()

    def test_database_constraint_blocks_zero_quantity(self, customer, product):
        with pytest.raises(IntegrityError):
            CartItem.objects.create(user=customer, product=product, quantity=0)


class TestUpdateRemoveSave:
    def test_update_quantity(self, customer_client, customer, product, fill_cart):
        item = fill_cart(customer, product)
        customer_client.post(reverse("cart:update", args=[item.pk]), {"quantity": 4})
        item.refresh_from_db()
        assert item.quantity == 4

    def test_update_rejects_over_stock_and_zero(self, customer_client, customer, make_product, fill_cart):
        product = make_product(stock=3)
        item = fill_cart(customer, product)
        customer_client.post(reverse("cart:update", args=[item.pk]), {"quantity": 9})
        customer_client.post(reverse("cart:update", args=[item.pk]), {"quantity": 0})
        item.refresh_from_db()
        assert item.quantity == 1

    def test_remove(self, customer_client, customer, product, fill_cart):
        item = fill_cart(customer, product)
        customer_client.post(reverse("cart:remove", args=[item.pk]))
        assert not CartItem.objects.exists()

    def test_save_for_later_and_back(self, customer_client, customer, product, fill_cart):
        item = fill_cart(customer, product)
        customer_client.post(reverse("cart:toggle_save", args=[item.pk]))
        item.refresh_from_db()
        assert item.is_saved_for_later
        summary = services.get_cart_summary(customer)
        assert summary.items == [] and summary.saved_items == [item]
        customer_client.post(reverse("cart:toggle_save", args=[item.pk]))
        item.refresh_from_db()
        assert not item.is_saved_for_later

    def test_adding_saved_item_moves_it_back(self, customer_client, customer, product, fill_cart):
        fill_cart(customer, product, 2, saved=True)
        add(customer_client, product, 1)
        item = CartItem.objects.get()
        assert not item.is_saved_for_later and item.quantity == 1

    def test_other_users_cannot_modify_cart(self, login, customer, other_customer, product, fill_cart):
        item = fill_cart(customer, product, 2)
        intruder = login(other_customer)
        assert intruder.post(reverse("cart:update", args=[item.pk]), {"quantity": 5}).status_code == 404
        assert intruder.post(reverse("cart:remove", args=[item.pk])).status_code == 404
        assert intruder.post(reverse("cart:toggle_save", args=[item.pk])).status_code == 404
        item.refresh_from_db()
        assert item.quantity == 2

    def test_state_changes_require_post(self, customer_client, customer, product, fill_cart):
        item = fill_cart(customer, product)
        assert customer_client.get(reverse("cart:remove", args=[item.pk])).status_code == 405


class TestSummary:
    def test_totals_use_live_prices_and_exclude_saved(self, customer, make_product, fill_cart):
        a = make_product(name="A", price="10.00")
        b = make_product(name="B", price="2.50")
        c = make_product(name="C", price="99.00")
        fill_cart(customer, a, 2)
        fill_cart(customer, b, 4)
        fill_cart(customer, c, 1, saved=True)
        summary = services.get_cart_summary(customer)
        assert summary.subtotal == Decimal("30.00")
        assert summary.total_quantity == 6
        a.price = Decimal("12.00")
        a.save()
        assert services.get_cart_summary(customer).subtotal == Decimal("34.00")

    def test_cart_page_and_empty_state(self, customer_client, customer, product, fill_cart):
        assert "Your cart is empty" in customer_client.get(reverse("cart:view")).content.decode()
        fill_cart(customer, product, 2)
        html = customer_client.get(reverse("cart:view")).content.decode()
        assert product.name in html and "$50.00" in html

    def test_cart_badge_counts_quantity(self, customer_client, customer, product, fill_cart):
        fill_cart(customer, product, 3)
        response = customer_client.get(reverse("core:home"))
        assert response.context["cart_count"] == 3

    def test_problem_detection(self, customer, make_product, fill_cart):
        product = make_product(stock=5)
        item = fill_cart(customer, product, 4)
        product.stock = 2
        product.save()
        item.refresh_from_db()
        assert item.problem == "Only 2 left in stock."
        assert services.get_cart_summary(customer).has_problems
