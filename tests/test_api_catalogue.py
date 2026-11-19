from decimal import Decimal

import pytest
from django.urls import reverse

from products.models import Category, Review, StockAlert

pytestmark = pytest.mark.django_db


def slugs(response):
    return [p["slug"] for p in response.json()["results"]]


def test_categories_only_active(api, category):
    Category.objects.create(name="Hidden", is_active=False)
    assert [c["slug"] for c in api().get(reverse("api:category-list")).json()] == ["kitchen"]


def test_product_list_visibility_and_pagination(api, make_product, pending_vendor):
    for i in range(3):
        make_product(name=f"Item {i}")
    make_product(name="Inactive", is_active=False)
    make_product(name="Pending", owner=pending_vendor)
    body = api().get(reverse("api:product-list"), {"page_size": 2}).json()
    assert body["count"] == 3 and len(body["results"]) == 2 and body["next"]


def test_product_filters_and_sort(api, make_product):
    make_product(name="Steel Pan", price="40.00")
    make_product(name="Steel Pot", price="15.00")
    make_product(name="Spoon", price="5.00")
    client = api()
    assert slugs(client.get(reverse("api:product-list"), {"q": "steel", "sort": "price_asc"})) == [
        "steel-pot", "steel-pan"]
    assert slugs(client.get(reverse("api:product-list"), {"max_price": "10"})) == ["spoon"]


def test_invalid_filters_return_400(api, product):
    response = api().get(reverse("api:product-list"), {"min_price": "50", "max_price": "1"})
    assert response.status_code == 400 and "max_price" in response.json()


def test_product_detail(api, variant_product):
    product, small, large = variant_product
    body = api().get(reverse("api:product-detail", args=[product.slug])).json()
    assert body["has_variants"] and len(body["variants"]) == 2
    assert {v["label"]: v["price"] for v in body["variants"]}["Size: L"] == "35.00"
    assert body["price"] == "30.00" and body["vendor"]["store_slug"] == "vera-goods"


def test_hidden_product_detail_404(api, make_product):
    product = make_product(is_active=False)
    assert api().get(reverse("api:product-detail", args=[product.slug])).status_code == 404


class TestReviews:
    def test_create_list_and_rating(self, api, customer, product):
        url = reverse("api:product-reviews", args=[product.slug])
        response = api(customer).post(url, {"rating": 4, "comment": "Solid knife, holds an edge."}, format="json")
        assert response.status_code == 201
        product.refresh_from_db()
        assert product.average_rating == Decimal("4.00")
        assert api().get(url).json()["count"] == 1

    def test_permissions_and_duplicates(self, api, customer, vendor, product):
        url = reverse("api:product-reviews", args=[product.slug])
        payload = {"rating": 5, "comment": "Fantastic product overall."}
        assert api().post(url, payload, format="json").status_code == 401
        assert api(vendor.user).post(url, payload, format="json").status_code == 403
        api(customer).post(url, payload, format="json")
        duplicate = api(customer).post(url, payload, format="json")
        assert duplicate.status_code == 409 and duplicate.json()["code"] == "duplicate_review"

    def test_validation(self, api, customer, product):
        url = reverse("api:product-reviews", args=[product.slug])
        response = api(customer).post(url, {"rating": 9, "comment": "short"}, format="json")
        assert response.status_code == 400 and set(response.json()) == {"rating", "comment"}

    def test_owner_only_edit_delete(self, api, customer, other_customer, product):
        review = Review.objects.create(product=product, user=customer, rating=5, comment="Great knife indeed")
        url = reverse("api:review-detail", args=[review.pk])
        assert api(other_customer).patch(url, {"rating": 1}, format="json").status_code == 404
        assert api(other_customer).delete(url).status_code == 404
        assert api(customer).patch(url, {"rating": 2}, format="json").json()["rating"] == 2
        assert api(customer).delete(url).status_code == 204
        product.refresh_from_db()
        assert product.review_count == 0


def test_questions(api, customer, product):
    url = reverse("api:product-questions", args=[product.slug])
    assert api(customer).post(url, {"question": "Is it dishwasher safe?"}, format="json").status_code == 201
    assert api().get(url).json()["results"][0]["is_answered"] is False


def test_stock_alert(api, customer, make_product, product):
    out = make_product(name="Gone", stock=0)
    client = api(customer)
    assert client.post(reverse("api:product-stock-alert", args=[out.slug])).status_code == 201
    assert client.post(reverse("api:product-stock-alert", args=[out.slug])).status_code == 200
    assert StockAlert.objects.count() == 1
    assert client.post(reverse("api:product-stock-alert", args=[product.slug])).status_code == 400


def test_stores(api, vendor, pending_vendor, product):
    client = api()
    assert [s["store_slug"] for s in client.get(reverse("api:store-list")).json()["results"]] == ["vera-goods"]
    assert client.get(reverse("api:store-detail", args=[pending_vendor.store_slug])).status_code == 404
    assert slugs(client.get(reverse("api:store-products", args=[vendor.store_slug]))) == [product.slug]
