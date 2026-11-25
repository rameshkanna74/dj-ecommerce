"""
Dashboard metrics computed with ORM aggregation.

Business definitions
--------------------
* **Recognised revenue** (platform): ``total_amount`` of orders that are *paid* and
  not cancelled. Summed on the Order table only, so joins cannot double count.
* **Gross sales** (vendor): price x quantity of the vendor's non-cancelled order
  lines, whether or not the order has been paid yet.
* **Revenue / net earnings** (vendor): gross value of non-cancelled lines in *paid*
  orders minus the platform commission captured on each line at purchase time.
  Coupons are funded by the platform and do not reduce vendor earnings.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from accounts.models import VendorProfile
from core.utils import money
from orders.models import Order, OrderItem
from products.models import Category, Product, Review

ZERO = Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2))
LINE_TOTAL = ExpressionWrapper(F("price") * F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=2))


def _net_earnings(lines):
    """
    Vendor net for ``lines``: each line total minus its commission rounded to the cent
    (exactly what ``OrderItem.vendor_earnings`` shows per line). Lines are grouped by
    (price, quantity, rate) in SQL so this stays one small query, and the rounding is done
    with Decimal in Python because SQLite's ROUND works on floats.
    """
    total = Decimal("0.00")
    for row in lines.values("price", "quantity", "commission_rate").annotate(n=Count("id")).order_by():
        line_total = row["price"] * row["quantity"]
        total += (line_total - money(line_total * row["commission_rate"] / Decimal("100"))) * row["n"]
    return money(total)


def _recognised_orders():
    return Order.objects.filter(payment_status=Order.PaymentStatus.PAID).exclude(status=Order.Status.CANCELLED)


def _live_lines():
    """Order lines that still count as sales (neither the line nor its order cancelled)."""
    return OrderItem.objects.exclude(status=OrderItem.Status.CANCELLED).exclude(order__status=Order.Status.CANCELLED)


def _fill_days(rows, days, value_key):
    """Return one point per day for the last ``days`` days, filling gaps with zero."""
    today = timezone.localdate()
    by_day = {row["day"]: row[value_key] or 0 for row in rows}
    return [
        {"label": day.strftime("%b %d"), "value": by_day.get(day, 0)}
        for day in (today - timedelta(days=offset) for offset in range(days - 1, -1, -1))
    ]


def admin_dashboard_data(days=30):
    User = get_user_model()
    since = timezone.now() - timedelta(days=days)

    users = User.objects.aggregate(
        customers=Count("id", filter=Q(role=User.Role.CUSTOMER)),
        vendors=Count("id", filter=Q(role=User.Role.VENDOR)),
    )
    vendors = VendorProfile.objects.aggregate(pending=Count("id", filter=Q(approval_status="pending")))
    products = Product.objects.with_available_stock().aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        out_of_stock=Count("id", filter=Q(is_active=True, available_stock__lte=0)),
    )
    orders = Order.objects.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=Order.Status.PENDING)),
        awaiting_payment=Count(
            "id", filter=Q(payment_status=Order.PaymentStatus.UNPAID) & ~Q(status=Order.Status.CANCELLED)
        ),
    )
    revenue = _recognised_orders().aggregate(
        total=Coalesce(Sum("total_amount"), ZERO), count=Count("id"), avg=Avg("total_amount")
    )

    trend_rows = (
        _recognised_orders()
        .filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total_amount"))
        .order_by("day")
    )

    top_products = (
        _live_lines()
        .values("product_id", "product_name")
        .annotate(units=Sum("quantity"), revenue=Sum(LINE_TOTAL))
        .order_by("-units", "-revenue")[:5]
    )
    category_performance = (
        _live_lines()
        .filter(order__payment_status=Order.PaymentStatus.PAID)
        .values("product__category__name")
        .annotate(units=Sum("quantity"), revenue=Sum(LINE_TOTAL))
        .order_by("-revenue")[:8]
    )

    return {
        "kpis": {
            "customers": users["customers"],
            "vendors": users["vendors"],
            "pending_vendors": vendors["pending"],
            "products": products["total"],
            "active_products": products["active"],
            "out_of_stock": products["out_of_stock"],
            "orders": orders["total"],
            "pending_orders": orders["pending"],
            "awaiting_payment": orders["awaiting_payment"],
            "revenue": revenue["total"],
            "paid_orders": revenue["count"],
            "avg_order_value": revenue["avg"] or Decimal("0.00"),
        },
        "recent_orders": Order.objects.select_related("user").order_by("-created_at")[:8],
        "top_products": list(top_products),
        "category_performance": [
            {"label": row["product__category__name"], "value": row["revenue"], "units": row["units"]}
            for row in category_performance
        ],
        "sales_trend": _fill_days(trend_rows, days, "total"),
        "pending_vendor_list": VendorProfile.objects.filter(approval_status="pending").select_related("user")[:5],
        "low_stock_products": Product.objects.with_available_stock()
        .filter(is_active=True, available_stock__lte=5)
        .select_related("vendor")
        .order_by("available_stock", "pk")[:6],
        "category_count": Category.objects.count(),
        "days": days,
    }


def vendor_dashboard_data(vendor, days=30):
    since = timezone.now() - timedelta(days=days)
    own_products = Product.objects.filter(vendor=vendor)
    own_lines = OrderItem.objects.filter(vendor=vendor)
    live = _live_lines().filter(vendor=vendor)

    product_stats = own_products.with_available_stock().aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        out_of_stock=Count("id", filter=Q(is_active=True, available_stock__lte=0)),
    )
    order_stats = own_lines.aggregate(
        orders=Count("order", distinct=True),
        pending_orders=Count("order", filter=Q(status=OrderItem.Status.PENDING), distinct=True),
        to_ship=Count("id", filter=Q(status__in=[OrderItem.Status.PENDING, OrderItem.Status.PROCESSING])),
    )
    sales = live.aggregate(units=Coalesce(Sum("quantity"), 0), gross=Coalesce(Sum(LINE_TOTAL), ZERO))
    paid_lines = live.filter(order__payment_status=Order.PaymentStatus.PAID)
    earnings = paid_lines.aggregate(recognised=Coalesce(Sum(LINE_TOTAL), ZERO))
    earnings["net"] = _net_earnings(paid_lines)
    rating = Review.objects.filter(product__vendor=vendor, is_visible=True).aggregate(
        avg=Avg("rating"), count=Count("id")
    )

    trend_rows = (
        live.filter(order__created_at__gte=since)
        .annotate(day=TruncDate("order__created_at"))
        .values("day")
        .annotate(total=Sum(LINE_TOTAL))
        .order_by("day")
    )
    best_sellers = (
        live.values("product_id", "product_name")
        .annotate(units=Sum("quantity"), revenue=Sum(LINE_TOTAL))
        .order_by("-units", "-revenue")[:5]
    )

    return {
        "kpis": {
            "total_products": product_stats["total"],
            "active_products": product_stats["active"],
            "out_of_stock": product_stats["out_of_stock"],
            "total_orders": order_stats["orders"],
            "pending_orders": order_stats["pending_orders"],
            "items_to_fulfil": order_stats["to_ship"],
            "units_sold": sales["units"],
            "gross_sales": sales["gross"],
            "recognised_sales": earnings["recognised"],
            "revenue": earnings["net"],
            "average_rating": round(rating["avg"] or 0, 2),
            "review_count": rating["count"],
        },
        "sales_trend": _fill_days(trend_rows, days, "total"),
        "best_sellers": [
            {"label": row["product_name"], "value": row["revenue"], "units": row["units"]} for row in best_sellers
        ],
        "recent_items": own_lines.select_related("order", "order__user").order_by("-order__created_at")[:8],
        "days": days,
    }
