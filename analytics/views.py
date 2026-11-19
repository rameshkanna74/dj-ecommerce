import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import admin_required, vendor_required
from orders.models import Order, OrderItem
from products.models import Product

from .services import admin_dashboard_data, vendor_dashboard_data

ALLOWED_RANGES = {7, 30, 90}


def _days(request):
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    return days if days in ALLOWED_RANGES else 30


def _csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe_cell(value) for value in row])
    return response


def _safe_cell(value):
    """Neutralise spreadsheet formula injection in exported text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@admin_required
def admin_dashboard(request):
    return render(request, "analytics/admin_dashboard.html", admin_dashboard_data(_days(request)))


@vendor_required
def vendor_analytics(request):
    vendor = request.user.vendor_profile
    return render(
        request,
        "analytics/vendor_dashboard.html",
        {"vendor": vendor, **vendor_dashboard_data(vendor, _days(request))},
    )


@admin_required
def export_orders(request):
    orders = Order.objects.select_related("user").order_by("-created_at")
    rows = (
        (
            o.order_number,
            timezone.localtime(o.created_at).strftime("%Y-%m-%d %H:%M"),
            o.user.username if o.user else (o.guest_email or ""),
            o.customer_name,
            o.get_status_display(),
            o.get_payment_status_display(),
            o.get_payment_method_display(),
            o.subtotal_amount,
            o.discount_amount,
            o.total_amount,
            o.coupon_code,
        )
        for o in orders.iterator()
    )
    header = ["Order", "Created", "Account", "Customer", "Status", "Payment", "Method", "Subtotal", "Discount",
              "Total", "Coupon"]
    return _csv_response(f"orders-{timezone.localdate()}.csv", header, rows)


@admin_required
def export_products(request):
    products = Product.objects.select_related("category", "vendor").with_units_sold().order_by("name")
    rows = (
        (
            p.pk,
            p.name,
            p.category.name,
            p.vendor.business_name if p.vendor else "CoreCart",
            p.price,
            p.stock,
            "yes" if p.is_active else "no",
            p.units_sold,
            p.average_rating,
            p.review_count,
        )
        for p in products
    )
    header = ["ID", "Name", "Category", "Vendor", "Price", "Stock", "Active", "Units sold", "Rating", "Reviews"]
    return _csv_response(f"products-{timezone.localdate()}.csv", header, rows)


@vendor_required
def vendor_export_sales(request):
    items = (
        OrderItem.objects.filter(vendor=request.user.vendor_profile)
        .select_related("order")
        .order_by("-order__created_at")
    )
    rows = (
        (
            i.order.order_number,
            timezone.localtime(i.order.created_at).strftime("%Y-%m-%d %H:%M"),
            i.display_name,
            i.variant_label,
            i.quantity,
            i.price,
            i.subtotal,
            i.commission_rate,
            i.vendor_earnings,
            i.get_status_display(),
            i.order.get_payment_status_display(),
            i.tracking_number or "",
        )
        for i in items.iterator()
    )
    header = ["Order", "Date", "Product", "Option", "Qty", "Unit price", "Line total", "Commission %", "Net earnings",
              "Item status", "Payment", "Tracking"]
    return _csv_response(f"sales-{timezone.localdate()}.csv", header, rows)
