from decimal import Decimal

import pytest
from django.urls import reverse

from orders.models import Order, OrderItem
from products.forms import ProductForm
from products.models import Category, Product, ProductVariant, Review, StockAlert

from .conftest import image_file, make_vendor

pytestmark = pytest.mark.django_db


class TestCatalogueVisibility:
    def test_visible_queryset_rules(self, make_product, vendor, pending_vendor, category):
        shown = make_product(name="Shown")
        make_product(name="Inactive", is_active=False)
        make_product(name="Pending vendor", owner=pending_vendor)
        hidden_cat = Category.objects.create(name="Hidden", is_active=False)
        make_product(name="Hidden category", category=hidden_cat)
        official = make_product(name="Official", owner=None)
        assert set(Product.objects.visible()) == {shown, official}

    def test_inactive_vendor_account_hides_products(self, product, vendor):
        vendor.user.is_active = False
        vendor.user.save()
        assert not Product.objects.visible().exists()

    def test_detail_404_for_hidden_products(self, client, make_product):
        product = make_product(is_active=False)
        assert client.get(product.get_absolute_url()).status_code == 404

    def test_detail_renders_and_tracks_recently_viewed(self, client, product):
        response = client.get(product.get_absolute_url())
        assert response.status_code == 200
        assert client.session["recently_viewed"] == [product.pk]


class TestListing:
    def test_search_category_price_filters(self, client, make_product, category):
        other = Category.objects.create(name="Garden")
        make_product(name="Steel Pan", price="40.00")
        make_product(name="Steel Rake", price="15.00", category=other)
        make_product(name="Wooden Spoon", price="5.00")

        names = lambda r: {p.name for p in r.context["products"]}  # noqa: E731
        assert names(client.get(reverse("products:list"), {"q": "steel"})) == {"Steel Pan", "Steel Rake"}
        assert names(client.get(reverse("products:list"), {"category": "garden"})) == {"Steel Rake"}
        assert names(client.get(reverse("products:list"), {"min_price": "10", "max_price": "20"})) == {"Steel Rake"}

    def test_invalid_price_range_reports_error(self, client, product):
        response = client.get(reverse("products:list"), {"min_price": "50", "max_price": "10"})
        assert response.status_code == 200
        assert "Max price must be greater" in response.content.decode()

    def test_garbage_filters_do_not_crash(self, client, product):
        response = client.get(reverse("products:list"), {"min_price": "abc", "sort": "drop table", "page": "x"})
        assert response.status_code == 200

    def test_sorting(self, client, make_product):
        make_product(name="Cheap", price="1.00")
        make_product(name="Pricey", price="99.00")
        asc = client.get(reverse("products:list"), {"sort": "price_asc"}).context["products"]
        desc = client.get(reverse("products:list"), {"sort": "price_desc"}).context["products"]
        assert asc[0].name == "Cheap" and desc[0].name == "Pricey"

    def test_popular_sort_uses_units_sold(self, client, make_product, customer):
        slow = make_product(name="Slow")
        fast = make_product(name="Fast")
        order = Order.objects.create(user=customer, total_amount=Decimal("50"))
        OrderItem.objects.create(order=order, product=fast, quantity=5, price=Decimal("10"))
        OrderItem.objects.create(order=order, product=slow, quantity=1, price=Decimal("10"))
        products = client.get(reverse("products:list"), {"sort": "popular"}).context["products"]
        assert [p.name for p in products][:2] == ["Fast", "Slow"]

    def test_pagination(self, client, make_product):
        for i in range(15):
            make_product(name=f"Item {i}")
        first = client.get(reverse("products:list"))
        second = client.get(reverse("products:list"), {"page": 2})
        assert len(first.context["products"]) == 12
        assert len(second.context["products"]) == 3
        assert first.context["is_paginated"]

    def test_empty_results_state(self, client, product):
        response = client.get(reverse("products:list"), {"q": "nothing-matches-this"})
        assert "No products match your search" in response.content.decode()

    def test_in_stock_filter_includes_variant_stock(self, client, make_product, variant_product):
        make_product(name="Empty", stock=0)
        names = {p.name for p in client.get(reverse("products:list"), {"in_stock": "on"}).context["products"]}
        assert "Linen Apron" in names and "Empty" not in names


class TestSlugs:
    def test_collision_safe_slugs(self, make_product):
        a = make_product(name="Mug")
        b = make_product(name="Mug")
        assert a.slug == "mug" and b.slug == "mug-2"

    def test_reserved_slug_avoided(self, make_product):
        assert make_product(name="New").slug == "new-2"


class TestProductForm:
    def test_rejects_non_positive_price(self, category):
        form = ProductForm(data={"category": category.pk, "name": "X", "description": "d", "price": "0",
                                 "stock": "1", "is_active": "on"})
        assert not form.is_valid() and "price" in form.errors

    def test_rejects_negative_stock(self, category):
        form = ProductForm(data={"category": category.pk, "name": "X", "description": "d", "price": "1",
                                 "stock": "-3"})
        assert not form.is_valid() and "stock" in form.errors

    def test_rejects_inactive_category(self, category):
        category.is_active = False
        category.save()
        form = ProductForm(data={"category": category.pk, "name": "X", "description": "d", "price": "1", "stock": "1"})
        assert not form.is_valid() and "category" in form.errors

    def test_image_validation(self, category, settings):
        data = {"category": category.pk, "name": "X", "description": "d", "price": "1", "stock": "1"}
        assert ProductForm(data=data, files={"cover_image": image_file()}).is_valid()

        bogus = image_file()
        bogus.name = "photo.exe"
        assert not ProductForm(data=data, files={"cover_image": bogus}).is_valid()

        settings.CORECART_MAX_IMAGE_SIZE = 10
        form = ProductForm(data=data, files={"cover_image": image_file()})
        assert not form.is_valid()
        assert "too large" in str(form.errors["cover_image"])

    def test_non_image_content_rejected(self, category):
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile("fake.png", b"not really an image", content_type="image/png")
        data = {"category": category.pk, "name": "X", "description": "d", "price": "1", "stock": "1"}
        assert not ProductForm(data=data, files={"cover_image": fake}).is_valid()


class TestReviews:
    def test_add_review_updates_rating(self, customer_client, customer, product):
        response = customer_client.post(
            reverse("products:add_review", args=[product.pk]), {"rating": 4, "comment": "Sharp and well balanced."}
        )
        assert response.status_code == 302
        product.refresh_from_db()
        assert product.review_count == 1 and product.average_rating == Decimal("4.00")
        assert not Review.objects.get().is_verified_purchase

    def test_one_review_per_customer(self, customer_client, product):
        url = reverse("products:add_review", args=[product.pk])
        customer_client.post(url, {"rating": 5, "comment": "Great product overall."})
        customer_client.post(url, {"rating": 1, "comment": "Trying a second time."})
        assert Review.objects.count() == 1

    def test_rating_bounds_and_comment_length(self, customer_client, product):
        url = reverse("products:add_review", args=[product.pk])
        customer_client.post(url, {"rating": 6, "comment": "Out of bounds rating."})
        customer_client.post(url, {"rating": 3, "comment": "short"})
        assert Review.objects.count() == 0

    def test_average_across_reviews_and_delete_recalculates(self, product, customer, other_customer):
        Review.objects.create(product=product, user=customer, rating=5, comment="Excellent knife")
        review = Review.objects.create(product=product, user=other_customer, rating=2, comment="Dull edge")
        product.refresh_from_db()
        assert product.average_rating == Decimal("3.50") and product.review_count == 2
        review.delete()
        product.refresh_from_db()
        assert product.average_rating == Decimal("5.00") and product.review_count == 1

    def test_hidden_reviews_excluded_from_rating(self, product, customer, other_customer):
        Review.objects.create(product=product, user=customer, rating=5, comment="Excellent knife")
        Review.objects.create(product=product, user=other_customer, rating=1, comment="Spam", is_visible=False)
        product.refresh_from_db()
        assert product.average_rating == Decimal("5.00") and product.review_count == 1

    def test_only_owner_can_edit_or_delete(self, login, customer, other_customer, product):
        review = Review.objects.create(product=product, user=customer, rating=5, comment="Excellent knife")
        intruder = login(other_customer)
        assert intruder.get(reverse("products:edit_review", args=[review.pk])).status_code == 404
        assert intruder.post(reverse("products:delete_review", args=[review.pk])).status_code == 404
        owner = login(customer)
        owner.post(reverse("products:edit_review", args=[review.pk]), {"rating": 3, "comment": "Edited my opinion."})
        review.refresh_from_db()
        assert review.rating == 3
        owner.post(reverse("products:delete_review", args=[review.pk]))
        assert not Review.objects.exists()

    def test_verified_purchase_flag(self, customer_client, customer, product):
        order = Order.objects.create(user=customer, total_amount=Decimal("25"))
        OrderItem.objects.create(order=order, product=product, quantity=1, price=Decimal("25"), status="delivered")
        customer_client.post(reverse("products:add_review", args=[product.pk]),
                             {"rating": 5, "comment": "Bought it and love it."})
        assert Review.objects.get().is_verified_purchase

    def test_vendor_cannot_review(self, vendor_client, product):
        response = vendor_client.post(reverse("products:add_review", args=[product.pk]),
                                      {"rating": 5, "comment": "My own product is great"})
        assert response.status_code == 403


class TestQuestionsAndAlerts:
    def test_question_and_vendor_answer(self, customer_client, login, vendor, product):
        customer_client.post(reverse("products:ask_question", args=[product.pk]), {"question": "Is it dishwasher safe?"})
        question = product.questions.get()
        vendor_client = login(vendor.user)
        vendor_client.post(reverse("products:answer_question", args=[question.pk]), {"answer": "Hand wash only."})
        question.refresh_from_db()
        assert question.is_answered and question.answer == "Hand wash only." and question.answered_by == vendor.user

    def test_vendor_cannot_answer_other_vendors_questions(self, login, other_vendor, customer, product):
        question = product.questions.create(user=customer, question="Is it sharp?")
        response = login(other_vendor.user).post(reverse("products:answer_question", args=[question.pk]),
                                                 {"answer": "Hijack"})
        assert response.status_code == 404

    def test_stock_alert_no_duplicates_and_single_notification(
        self, customer_client, customer, make_product, mailoutbox, django_capture_on_commit_callbacks
    ):
        product = make_product(stock=0)
        url = reverse("products:stock_alert", args=[product.pk])
        customer_client.post(url)
        customer_client.post(url)
        assert StockAlert.objects.count() == 1

        with django_capture_on_commit_callbacks(execute=True):
            product.stock = 5
            product.save()
        assert len(mailoutbox) == 1
        assert "Back in stock" in mailoutbox[0].subject
        assert StockAlert.objects.get().notified_at is not None

        with django_capture_on_commit_callbacks(execute=True):
            product.stock = 6
            product.save()
        assert len(mailoutbox) == 1

    def test_variant_restock_triggers_alert(self, customer, variant_product, mailoutbox,
                                            django_capture_on_commit_callbacks):
        product, small, large = variant_product
        ProductVariant.objects.filter(product=product).update(stock=0)
        StockAlert.objects.create(user=customer, product=product)
        small.refresh_from_db()
        with django_capture_on_commit_callbacks(execute=True):
            small.stock = 4
            small.save()
        assert len(mailoutbox) == 1


class TestCategories:
    def test_category_with_products_is_protected(self, product, category):
        from django.db.models import ProtectedError

        with pytest.raises(ProtectedError):
            category.delete()

    def test_navigation_cache_invalidated_on_change(self, client, category):
        assert "Kitchen" in client.get(reverse("core:home")).content.decode()
        category.name = "Cookware"
        category.save()
        html = client.get(reverse("core:home")).content.decode()
        assert "Cookware" in html


def test_official_products_have_no_vendor(make_product):
    assert make_product(owner=None).vendor is None


def test_vendor_factory_unique(db):
    assert make_vendor("zed").store_slug == "zed-goods"
