from decimal import Decimal

import pytest
from django.urls import reverse

from orders import payments, services
from orders.models import Coupon, Order, OrderItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def placed_order(customer, make_product, fill_cart, shipping, vendor, other_vendor):
    mine = make_product(name="Mine", price="20.00", stock=10)
    theirs = make_product(name="Theirs", price="5.00", stock=10, owner=other_vendor)
    fill_cart(customer, mine, 2)
    fill_cart(customer, theirs, 1)
    order, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="p1")
    return order


def item_for(order, name):
    return order.items.get(product_name=name)


class TestOwnership:
    def test_customer_sees_only_own_orders(self, login, customer, other_customer, placed_order):
        assert login(customer).get(placed_order.get_absolute_url()).status_code == 200
        intruder = login(other_customer)
        assert intruder.get(placed_order.get_absolute_url()).status_code == 404
        assert intruder.get(reverse("orders:invoice", args=[placed_order.order_number])).status_code == 404
        assert placed_order not in intruder.get(reverse("orders:list")).context["orders"]

    def test_invoice_access(self, login, customer, admin_user, vendor, placed_order):
        url = reverse("orders:invoice", args=[placed_order.order_number])
        response = login(customer).get(url)
        assert response.status_code == 200 and placed_order.order_number in response.content.decode()
        assert login(admin_user).get(url).status_code == 200
        assert login(vendor.user).get(url).status_code == 404

    def test_vendor_sees_only_own_items(self, login, vendor, other_vendor, placed_order):
        client = login(vendor.user)
        items = list(client.get(reverse("orders:vendor_order_list")).context["order_items"])
        assert [i.product_name for i in items] == ["Mine"]
        detail = client.get(reverse("orders:vendor_order_detail", args=[placed_order.order_number]))
        assert detail.status_code == 200
        html = detail.content.decode()
        assert "Mine" in html and "Theirs" not in html

    def test_vendor_cannot_update_other_vendors_items(self, login, vendor, placed_order):
        theirs = item_for(placed_order, "Theirs")
        response = login(vendor.user).post(
            reverse("orders:vendor_update_item", args=[theirs.pk]), {f"item-{theirs.pk}-status": "processing"}
        )
        assert response.status_code == 404
        theirs.refresh_from_db()
        assert theirs.status == "pending"

    def test_vendor_without_items_gets_404(self, login, make_product, placed_order):
        from .conftest import make_vendor

        stranger = make_vendor("stranger")
        assert login(stranger.user).get(
            reverse("orders:vendor_order_detail", args=[placed_order.order_number])
        ).status_code == 404


class TestStatusWorkflow:
    def test_vendor_moves_item_through_workflow(self, login, vendor, placed_order):
        client = login(vendor.user)
        item = item_for(placed_order, "Mine")
        url = reverse("orders:vendor_update_item", args=[item.pk])
        prefix = f"item-{item.pk}"

        client.post(url, {f"{prefix}-status": "processing"})
        item.refresh_from_db()
        placed_order.refresh_from_db()
        assert item.status == "processing" and placed_order.status == "processing"

        client.post(url, {f"{prefix}-status": "shipped"})  # missing tracking number
        item.refresh_from_db()
        assert item.status == "processing"

        client.post(url, {f"{prefix}-status": "shipped", f"{prefix}-tracking_number": "TRK123"})
        item.refresh_from_db()
        placed_order.refresh_from_db()
        assert item.status == "shipped" and item.tracking_number == "TRK123"
        assert placed_order.status == "processing"  # other vendor's item still pending
        assert placed_order.tracking_number == "TRK123"

    def test_invalid_transitions_rejected(self, vendor, placed_order):
        item = item_for(placed_order, "Mine")
        with pytest.raises(services.OrderWorkflowError):
            services.set_item_status(item, "delivered", vendor.user)
        services.set_item_status(item, "processing", vendor.user)
        services.set_item_status(item, "shipped", vendor.user, "T1")
        services.set_item_status(item, "delivered", vendor.user)
        with pytest.raises(services.OrderWorkflowError):
            services.set_item_status(item, "pending", vendor.user)

    def test_parent_status_derivation(self):
        derive = services.derive_order_status
        assert derive(["pending", "pending"]) == "pending"
        assert derive(["processing", "pending"]) == "processing"
        assert derive(["shipped", "delivered"]) == "shipped"
        assert derive(["delivered", "delivered"]) == "delivered"
        assert derive(["delivered", "cancelled"]) == "delivered"
        assert derive(["cancelled", "cancelled"]) == "cancelled"

    def test_full_delivery_updates_order_and_timeline(self, vendor, other_vendor, placed_order):
        for item, actor in ((item_for(placed_order, "Mine"), vendor.user), (item_for(placed_order, "Theirs"),
                                                                           other_vendor.user)):
            services.set_item_status(item, "processing", actor)
            services.set_item_status(item, "shipped", actor, "T")
            services.set_item_status(item, "delivered", actor)
        placed_order.refresh_from_db()
        assert placed_order.status == "delivered"
        notes = list(placed_order.timeline.values_list("note", flat=True))
        assert any("Delivered" in n for n in notes) and len(notes) >= 7

    def test_vendor_item_cancellation_restocks_and_recalculates(self, vendor, placed_order):
        item = item_for(placed_order, "Mine")
        services.set_item_status(item, "cancelled", vendor.user)
        item.product.refresh_from_db()
        assert item.product.stock == 10
        placed_order.refresh_from_db()
        assert placed_order.subtotal_amount == Decimal("5.00") and placed_order.total_amount == Decimal("5.00")
        assert placed_order.status == "pending"

    def test_status_change_emails_customer(self, vendor, placed_order, mailoutbox,
                                          django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            services.set_item_status(item_for(placed_order, "Mine"), "processing", vendor.user)
        assert any("processing" in m.subject for m in mailoutbox)


class TestCancellation:
    def test_customer_cancels_pending_order(self, login, customer, placed_order, make_coupon):
        response = login(customer).post(reverse("orders:cancel", args=[placed_order.order_number]),
                                        {"reason": "Changed my mind"})
        assert response.status_code == 302
        placed_order.refresh_from_db()
        assert placed_order.status == "cancelled" and placed_order.cancelled_at
        assert set(placed_order.items.values_list("status", flat=True)) == {"cancelled"}
        assert item_for(placed_order, "Mine").product.stock == 10
        assert "Changed my mind" in placed_order.timeline.first().note

    def test_cancel_releases_coupon(self, customer, make_product, fill_cart, shipping, make_coupon):
        make_coupon(code="SAVE10")
        fill_cart(customer, make_product())
        order, _ = services.place_order(customer, shipping=shipping, payment_method="cod", coupon_code="SAVE10",
                                        checkout_token="c")
        assert Coupon.objects.get().used_count == 1
        services.cancel_order(order, customer)
        assert Coupon.objects.get().used_count == 0

    def test_cannot_cancel_once_processing(self, login, customer, vendor, placed_order):
        services.set_item_status(item_for(placed_order, "Mine"), "processing", vendor.user)
        placed_order.refresh_from_db()
        assert not placed_order.can_customer_cancel()
        login(customer).post(reverse("orders:cancel", args=[placed_order.order_number]))
        placed_order.refresh_from_db()
        assert placed_order.status != "cancelled"

    def test_other_customer_cannot_cancel(self, login, other_customer, placed_order):
        assert login(other_customer).post(
            reverse("orders:cancel", args=[placed_order.order_number])
        ).status_code == 404

    def test_paid_orders_cannot_be_cancelled(self, admin_user, placed_order):
        payments.mark_order_paid(placed_order, admin_user)
        with pytest.raises(services.OrderWorkflowError):
            services.cancel_order(placed_order, admin_user)


class TestPayments:
    def test_mark_paid_records_timeline(self, admin_user, placed_order):
        payments.mark_order_paid(placed_order, admin_user, reference="BANK-42")
        placed_order.refresh_from_db()
        assert placed_order.is_paid and placed_order.paid_at and placed_order.payment_reference == "BANK-42"
        assert "Payment received" in placed_order.timeline.first().note

    def test_cancelled_order_cannot_be_paid(self, admin_user, customer, placed_order):
        services.cancel_order(placed_order, customer)
        with pytest.raises(payments.PaymentError):
            payments.mark_order_paid(placed_order, admin_user)

    def test_admin_action_marks_paid(self, login, admin_user, placed_order):
        client = login(admin_user)
        response = client.post(
            reverse("admin:orders_order_changelist"),
            {"action": "mark_paid", "_selected_action": [placed_order.pk]},
        )
        assert response.status_code == 302
        placed_order.refresh_from_db()
        assert placed_order.is_paid

    def test_admin_item_edit_goes_through_workflow(self, login, admin_user, placed_order):
        item = item_for(placed_order, "Mine")
        client = login(admin_user)
        url = reverse("admin:orders_orderitem_change", args=[item.pk])
        client.post(url, {"status": "delivered", "tracking_number": ""})
        item.refresh_from_db()
        assert item.status == "pending"
        client.post(url, {"status": "processing", "tracking_number": ""})
        item.refresh_from_db()
        assert item.status == "processing"
        assert OrderItem.objects.get(pk=item.pk).order.status == "processing"

    def test_order_list_and_detail_render(self, login, customer, placed_order):
        client = login(customer)
        assert placed_order.order_number in client.get(reverse("orders:list")).content.decode()
        html = client.get(placed_order.get_absolute_url()).content.decode()
        assert "Cash on delivery" in html and "Awaiting payment" in html and "Order placed" in html

    def test_order_status_filter(self, login, customer, placed_order):
        response = login(customer).get(reverse("orders:list"), {"status": "delivered"})
        assert list(response.context["orders"]) == []


def test_order_number_unique(customer):
    a = Order.objects.create(user=customer, total_amount=Decimal("1"))
    b = Order.objects.create(user=customer, total_amount=Decimal("1"))
    assert a.order_number != b.order_number
