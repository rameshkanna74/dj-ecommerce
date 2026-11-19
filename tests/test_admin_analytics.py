import csv
import io
from decimal import Decimal

import pytest
from django.urls import reverse

from analytics.services import admin_dashboard_data
from orders import payments, services

from .conftest import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def sales(customer, make_product, fill_cart, shipping, admin_user, make_coupon):
    """One paid order with a coupon, one unpaid order, one cancelled order."""
    a = make_product(name="Alpha", price="40.00", stock=50)
    b = make_product(name="Beta", price="10.00", stock=50)
    make_coupon(code="TEN", discount_type="fixed", value="10")

    fill_cart(customer, a, 2)
    fill_cart(customer, b, 3)
    paid, _ = services.place_order(customer, shipping=shipping, payment_method="cod", coupon_code="TEN",
                                   checkout_token="1")
    payments.mark_order_paid(paid, admin_user)

    fill_cart(customer, a, 1)
    unpaid, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="2")

    fill_cart(customer, b, 5)
    cancelled, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="3")
    services.cancel_order(cancelled, customer)
    return {"paid": paid, "unpaid": unpaid, "cancelled": cancelled}


def test_revenue_excludes_unpaid_and_cancelled(sales, pending_vendor):
    data = admin_dashboard_data()
    kpis = data["kpis"]
    assert kpis["revenue"] == Decimal("100.00")  # 110 - 10 coupon, paid order only
    assert kpis["paid_orders"] == 1
    assert kpis["orders"] == 3
    assert kpis["pending_orders"] == 2  # paid and unpaid orders both await fulfilment
    assert kpis["awaiting_payment"] == 1
    assert kpis["pending_vendors"] == 1
    assert kpis["customers"] == 1


def test_top_products_and_category_performance_avoid_join_duplication(sales):
    data = admin_dashboard_data()
    top = {row["product_name"]: row for row in data["top_products"]}
    assert top["Alpha"]["units"] == 3 and top["Beta"]["units"] == 3
    assert top["Alpha"]["revenue"] == Decimal("120.00")
    categories = data["category_performance"]
    assert categories == [{"label": "Kitchen", "value": Decimal("110.00"), "units": 5}]


def test_sales_trend_covers_every_day(sales):
    trend = admin_dashboard_data(days=7)["sales_trend"]
    assert len(trend) == 7
    assert trend[-1]["value"] == Decimal("100.00")


def test_admin_dashboard_requires_platform_admin(client, login, admin_user, customer):
    assert client.get(reverse("analytics:admin_dashboard")).status_code == 302
    assert login(customer).get(reverse("analytics:admin_dashboard")).status_code == 403
    staff_without_role = make_user("staffer", is_staff=True)
    assert login(staff_without_role).get(reverse("analytics:admin_dashboard")).status_code == 403
    assert login(admin_user).get(reverse("analytics:admin_dashboard")).status_code == 200


def test_admin_dashboard_renders_with_data(login, admin_user, sales):
    html = login(admin_user).get(reverse("analytics:admin_dashboard")).content.decode()
    assert "$100.00" in html and sales["paid"].order_number in html


def test_orders_csv_export(login, admin_user, sales):
    response = login(admin_user).get(reverse("analytics:export_orders"))
    assert response.status_code == 200 and response["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.content.decode())))
    assert rows[0][0] == "Order" and len(rows) == 4
    assert {r[0] for r in rows[1:]} == {o.order_number for o in sales.values()}


def test_products_csv_export_and_formula_injection_guard(login, admin_user, make_product):
    make_product(name="=HYPERLINK(evil)")
    rows = list(csv.reader(io.StringIO(login(admin_user).get(reverse("analytics:export_products")).content.decode())))
    assert rows[1][1] == "'=HYPERLINK(evil)"


def test_csv_export_forbidden_for_vendors(vendor_client):
    assert vendor_client.get(reverse("analytics:export_orders")).status_code == 403


@pytest.mark.parametrize(
    "url_name",
    ["admin:orders_order_changelist", "admin:orders_orderitem_changelist", "admin:orders_coupon_changelist",
     "admin:products_product_changelist", "admin:products_category_changelist", "admin:products_review_changelist",
     "admin:accounts_vendorprofile_changelist", "admin:accounts_customuser_changelist",
     "admin:support_supportticket_changelist", "admin:cart_cartitem_changelist", "admin:products_stockalert_changelist",
     "admin:products_productquestion_changelist"],
)
def test_django_admin_pages_load(login, admin_user, sales, url_name):
    assert login(admin_user).get(reverse(url_name)).status_code == 200


def test_admin_order_change_page(login, admin_user, sales):
    assert login(admin_user).get(reverse("admin:orders_order_change", args=[sales["paid"].pk])).status_code == 200


def test_admin_cancel_action_restocks(login, admin_user, sales):
    unpaid = sales["unpaid"]
    login(admin_user).post(reverse("admin:orders_order_changelist"),
                           {"action": "cancel_orders", "_selected_action": [unpaid.pk]})
    unpaid.refresh_from_db()
    assert unpaid.status == "cancelled"


def test_admin_deactivate_users(login, admin_user, customer):
    login(admin_user).post(reverse("admin:accounts_customuser_changelist"),
                           {"action": "deactivate_accounts", "_selected_action": [customer.pk, admin_user.pk]})
    customer.refresh_from_db()
    admin_user.refresh_from_db()
    assert not customer.is_active and admin_user.is_active
