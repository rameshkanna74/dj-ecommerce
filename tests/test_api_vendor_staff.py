from decimal import Decimal

import pytest
from django.urls import reverse

from orders import payments, services
from orders.models import Order
from products.models import Product, Review

from .conftest import image_file

pytestmark = pytest.mark.django_db


@pytest.fixture
def placed_order(customer, product, make_product, other_vendor, fill_cart, shipping):
    fill_cart(customer, product, 2)
    fill_cart(customer, make_product(name="Theirs", owner=other_vendor))
    order, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="v1")
    return order


class TestVendorAccess:
    def test_pending_vendor(self, api, pending_vendor):
        client = api(pending_vendor.user)
        assert client.get(reverse("api:vendor-application")).json()["approval_status"] == "pending"
        assert client.get(reverse("api:vendor-product-list")).status_code == 403
        assert client.get(reverse("api:vendor-dashboard")).status_code == 403

    def test_customer_blocked(self, api, customer):
        assert api(customer).get(reverse("api:vendor-product-list")).status_code == 403
        assert api(customer).get(reverse("api:vendor-application")).status_code == 403


class TestVendorProducts:
    def test_create_assigns_owner(self, api, vendor, other_vendor, category):
        response = api(vendor.user).post(
            reverse("api:vendor-product-list"),
            {"name": "Copper Pot", "category": category.pk, "description": "Heavy", "price": "80.00", "stock": 3,
             "vendor": other_vendor.pk, "is_featured": True},
            format="json",
        )
        assert response.status_code == 201
        product = Product.objects.get()
        assert product.vendor == vendor and not product.is_featured and product.slug == "copper-pot"

    def test_validation(self, api, vendor, category):
        category.is_active = False
        category.save()
        response = api(vendor.user).post(reverse("api:vendor-product-list"),
                                         {"name": "X", "category": category.pk, "description": "d", "price": "0",
                                          "stock": -1}, format="json")
        assert response.status_code == 400 and {"category", "price", "stock"} <= set(response.json())

    def test_cross_vendor_isolation(self, api, other_vendor, product):
        client = api(other_vendor.user)
        assert client.get(reverse("api:vendor-product-list")).json()["count"] == 0
        url = reverse("api:vendor-product-detail", args=[product.pk])
        assert client.patch(url, {"price": "1.00"}, format="json").status_code == 404
        assert client.delete(url).status_code == 404
        assert client.post(reverse("api:vendor-variant-list", args=[product.pk]),
                           {"attribute_name": "Size", "attribute_value": "S"}, format="json").status_code == 404

    def test_variants_and_images(self, api, vendor, product, settings):
        client = api(vendor.user)
        url = reverse("api:vendor-variant-list", args=[product.pk])
        payload = {"attribute_name": "Size", "attribute_value": "S", "stock": 4, "price_override": "30.00"}
        assert client.post(url, payload, format="json").status_code == 201
        assert client.post(url, payload, format="json").status_code == 400
        images = reverse("api:vendor-image-list", args=[product.pk])
        assert client.post(images, {"image": image_file(), "alt_text": "Side"}, format="multipart").status_code == 201
        settings.CORECART_MAX_IMAGE_SIZE = 10
        assert client.post(images, {"image": image_file()}, format="multipart").status_code == 400

    def test_delete_with_orders_hides(self, api, vendor, product, placed_order):
        response = api(vendor.user).delete(reverse("api:vendor-product-detail", args=[product.pk]))
        assert response.status_code == 200 and response.json()["code"] == "hidden_instead"
        product.refresh_from_db()
        assert not product.is_active


class TestVendorOrders:
    def test_items_and_order_scoped(self, api, vendor, placed_order):
        client = api(vendor.user)
        items = client.get(reverse("api:vendor-order-items")).json()["results"]
        assert [i["product_name"] for i in items] == ["Chef Knife"]
        assert items[0]["allowed_next_statuses"] == ["cancelled", "processing"]
        detail = client.get(reverse("api:vendor-order-detail", args=[placed_order.order_number])).json()
        assert [i["product_name"] for i in detail["items"]] == ["Chef Knife"]

    def test_status_workflow(self, api, vendor, other_vendor, placed_order):
        mine = placed_order.items.get(product_name="Chef Knife")
        theirs = placed_order.items.get(product_name="Theirs")
        client = api(vendor.user)
        url = reverse("api:vendor-order-item-status", args=[mine.pk])
        assert client.post(reverse("api:vendor-order-item-status", args=[theirs.pk]),
                           {"status": "processing"}, format="json").status_code == 404
        bad = client.post(url, {"status": "delivered"}, format="json")
        assert bad.status_code == 409 and bad.json()["code"] == "invalid_transition"
        assert client.post(url, {"status": "processing"}, format="json").json()["status"] == "processing"
        assert client.post(url, {"status": "shipped"}, format="json").status_code == 409  # tracking required
        assert client.post(url, {"status": "shipped", "tracking_number": "T1"}, format="json").status_code == 200

    def test_dashboard(self, api, vendor, admin_user, placed_order):
        payments.mark_order_paid(placed_order, admin_user)
        body = api(vendor.user).get(reverse("api:vendor-dashboard"), {"days": 7}).json()
        assert body["kpis"]["gross_sales"] == "50.00" and body["kpis"]["revenue"] == "45.00"
        assert len(body["sales_trend"]) == 7

    def test_answer_question(self, api, vendor, customer, product):
        question = product.questions.create(user=customer, question="Is it sharp?")
        response = api(vendor.user).post(reverse("api:vendor-question-answer", args=[question.pk]),
                                         {"answer": "Very."}, format="json")
        assert response.json()["is_answered"] is True


class TestStaff:
    @pytest.mark.parametrize("url_name", ["api:staff-dashboard", "api:staff-order-list", "api:staff-vendor-list",
                                          "api:staff-user-list", "api:staff-ticket-list"])
    def test_non_admins_forbidden(self, api, customer, vendor, url_name):
        assert api(customer).get(reverse(url_name)).status_code == 403
        assert api(vendor.user).get(reverse(url_name)).status_code == 403

    def test_vendor_approval(self, api, admin_user, pending_vendor, mailoutbox):
        client = api(admin_user)
        assert client.get(reverse("api:staff-vendor-list"), {"status": "pending"}).json()["count"] == 1
        body = client.post(reverse("api:staff-vendor-approve", args=[pending_vendor.pk])).json()
        assert body["approval_status"] == "approved" and mailoutbox
        assert client.post(reverse("api:staff-vendor-reject", args=[pending_vendor.pk])).status_code == 409
        body = client.post(reverse("api:staff-vendor-suspend", args=[pending_vendor.pk]), {"reason": "Policy"},
                           format="json").json()
        assert body["approval_status"] == "suspended" and body["rejection_reason"] == "Policy"

    def test_orders_payment_and_cancel(self, api, admin_user, placed_order):
        client = api(admin_user)
        url = reverse("api:staff-order-detail", args=[placed_order.order_number])
        assert client.get(url).status_code == 200
        paid = client.post(reverse("api:staff-order-mark-paid", args=[placed_order.order_number]),
                           {"reference": "BANK-1"}, format="json").json()
        assert paid["payment_status"] == "paid"
        cancel = client.post(reverse("api:staff-order-cancel", args=[placed_order.order_number]))
        assert cancel.status_code == 409  # paid orders must be refunded first
        client.post(reverse("api:staff-order-refund", args=[placed_order.order_number]))
        assert client.post(reverse("api:staff-order-cancel", args=[placed_order.order_number])).status_code == 200
        assert Order.objects.get().status == "cancelled"

    def test_dashboard_revenue(self, api, admin_user, placed_order):
        payments.mark_order_paid(placed_order, admin_user)
        kpis = api(admin_user).get(reverse("api:staff-dashboard")).json()["kpis"]
        assert kpis["revenue"] == "75.00" and kpis["paid_orders"] == 1

    def test_coupon_validation(self, api, admin_user):
        payload = {"code": "half", "discount_type": "percentage", "value": "150", "valid_from": "2026-01-01T00:00:00Z",
                   "valid_to": "2025-01-01T00:00:00Z", "usage_limit": 5}
        response = api(admin_user).post(reverse("api:staff-coupon-list"), payload, format="json")
        assert response.status_code == 400 and "valid_to" in response.json()
        payload.update(value="50", valid_to="2027-01-01T00:00:00Z")
        assert api(admin_user).post(reverse("api:staff-coupon-list"), payload, format="json").json()["code"] == "HALF"

    def test_category_delete_protected(self, api, admin_user, category, product):
        response = api(admin_user).delete(reverse("api:staff-category-detail", args=[category.pk]))
        assert response.status_code == 409 and response.json()["code"] == "protected"

    def test_user_status(self, api, admin_user, customer):
        client = api(admin_user)
        assert client.patch(reverse("api:staff-user-detail", args=[customer.pk]), {"is_active": False, "role": "admin"},
                            format="json").status_code == 200
        customer.refresh_from_db()
        assert not customer.is_active and customer.role == "customer"
        assert client.patch(reverse("api:staff-user-detail", args=[admin_user.pk]), {"is_active": False},
                            format="json").status_code == 400

    def test_review_moderation_updates_rating(self, api, admin_user, customer, product):
        review = Review.objects.create(product=product, user=customer, rating=1, comment="Spammy review text")
        api(admin_user).patch(reverse("api:staff-review-detail", args=[review.pk]), {"is_visible": False},
                              format="json")
        product.refresh_from_db()
        assert product.review_count == 0 and product.average_rating == Decimal("0")

    def test_feature_product(self, api, admin_user, product):
        api(admin_user).patch(reverse("api:staff-product-detail", args=[product.pk]), {"is_featured": True,
                                                                                         "price": "1"}, format="json")
        product.refresh_from_db()
        assert product.is_featured and product.price == Decimal("25.00")


class TestSupportApi:
    def test_ticket_lifecycle(self, api, customer, other_customer, admin_user, placed_order):
        client = api(customer)
        response = client.post(reverse("api:ticket-list"),
                               {"subject": "Late", "message": "My parcel has not arrived yet.",
                                "order": placed_order.order_number}, format="json")
        assert response.status_code == 201
        ticket_id = response.json()["id"]
        assert api(other_customer).get(reverse("api:ticket-detail", args=[ticket_id])).status_code == 404

        staff = api(admin_user)
        body = staff.post(reverse("api:staff-ticket-respond", args=[ticket_id]),
                          {"body": "Shipped today.", "status": "resolved"}, format="json").json()
        assert body["status"] == "resolved" and body["messages"][0]["author"] == "CoreCart Support"
        bad = staff.post(reverse("api:staff-ticket-respond", args=[ticket_id]), {"status": "open"}, format="json")
        assert bad.status_code == 400 and bad.json()["code"] == "ticket_error"

        assert client.post(reverse("api:ticket-reply", args=[ticket_id]), {"body": "Still waiting"},
                           format="json").status_code == 201
        assert client.get(reverse("api:ticket-detail", args=[ticket_id])).json()["status"] == "open"
        assert client.post(reverse("api:ticket-close", args=[ticket_id])).json()["status"] == "closed"

    def test_cannot_attach_foreign_order(self, api, other_customer, placed_order):
        response = api(other_customer).post(reverse("api:ticket-list"),
                                            {"subject": "Hi", "message": "Question about an order.",
                                             "order": placed_order.order_number}, format="json")
        assert response.status_code == 400 and "order" in response.json()


def test_schema_and_docs_and_health(api):
    client = api()
    schema = client.get(reverse("api:schema"), HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert schema.status_code == 200
    assert "/api/v1/checkout/" in schema.content.decode()
    assert client.get(reverse("api:docs")).status_code == 200
    assert client.get(reverse("api:health")).json() == {"status": "ok", "version": "1.0.0"}
