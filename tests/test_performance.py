"""Query-count guards: page cost must not grow with the number of rows (no N+1)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from orders import services
from products.models import Product, ProductVariant, Review

from .conftest import make_user

pytestmark = pytest.mark.django_db


def count_queries(client, url):
    client.get(url)  # warm caches (navigation categories, session)
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
    assert response.status_code == 200
    return len(ctx.captured_queries)


def seed_products(make_product, start, count):
    for i in range(start, start + count):
        product = make_product(name=f"Product {i}")
        ProductVariant.objects.create(product=product, attribute_name="Size", attribute_value="M", stock=2)
        Review.objects.create(product=product, user=make_user(f"rev{i}"), rating=4, comment="Nice product here")


@pytest.mark.parametrize("url_name", ["core:home", "products:list"])
def test_catalogue_pages_constant_queries(client, make_product, url_name):
    seed_products(make_product, 0, 2)
    small = count_queries(client, reverse(url_name))
    seed_products(make_product, 2, 8)
    assert count_queries(client, reverse(url_name)) == small


def api_query_count(client, url):
    client.get(url)
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx.captured_queries)


def test_api_lists_constant_queries(api, customer, vendor, make_product, fill_cart, shipping):
    seed_products(make_product, 0, 2)
    for product in list(Product.objects.all()):
        fill_cart(customer, product, variant=product.variants.first())
    services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="a1")
    for product in Product.objects.all()[:2]:
        fill_cart(customer, product, variant=product.variants.first())
    urls = [reverse("api:product-list"), reverse("api:vendor-product-list"), reverse("api:vendor-order-items"),
            reverse("api:orders"), reverse("api:cart")]
    clients = [api(), api(vendor.user), api(vendor.user), api(customer), api(customer)]
    before = [api_query_count(c, u) for c, u in zip(clients, urls)]

    seed_products(make_product, 2, 8)
    for product in Product.objects.exclude(order_items__isnull=False).exclude(cart_items__isnull=False):
        fill_cart(customer, product, variant=product.variants.first())
    services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="a2")
    for product in Product.objects.all()[:6]:
        fill_cart(customer, product, variant=product.variants.first())
    assert [api_query_count(c, u) for c, u in zip(clients, urls)] == before


def test_cart_and_vendor_lists_constant_queries(login, customer, vendor, make_product, fill_cart, shipping):
    customer_client = login(customer)
    for i in range(2):
        fill_cart(customer, make_product(name=f"C{i}"))
    small = count_queries(customer_client, reverse("cart:view"))
    for i in range(2, 8):
        fill_cart(customer, make_product(name=f"C{i}"))
    assert count_queries(customer_client, reverse("cart:view")) == small

    services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="q1")
    vendor_client = login(vendor.user)
    vendor_small = count_queries(vendor_client, reverse("orders:vendor_order_list"))
    products_small = count_queries(vendor_client, reverse("products:vendor_list"))
    for i in range(8, 14):
        fill_cart(customer, make_product(name=f"C{i}"))
    services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="q2")
    assert count_queries(vendor_client, reverse("orders:vendor_order_list")) == vendor_small
    assert count_queries(vendor_client, reverse("products:vendor_list")) == products_small
