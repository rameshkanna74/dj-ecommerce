"""Dashboard metrics as JSON. Money values are serialised as decimal strings."""

from decimal import Decimal

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.permissions import IsPlatformAdmin, VendorScopedMixin
from orders.api import OrderSummarySerializer

from .services import admin_dashboard_data, vendor_dashboard_data

DAYS_PARAM = OpenApiParameter("days", int, enum=[7, 30, 90], description="Trend window (default 30)")
DASHBOARD_RESPONSE = {200: {"type": "object", "additionalProperties": True}}


def _days(request):
    try:
        days = int(request.query_params.get("days", 30))
    except ValueError:
        return 30
    return days if days in {7, 30, 90} else 30


def plain(value):
    """Recursively convert Decimals to strings so money keeps its exact value in JSON."""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


class AdminDashboardView(APIView):
    """Marketplace KPIs. Revenue counts only paid, non-cancelled orders."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(parameters=[DAYS_PARAM], responses=DASHBOARD_RESPONSE)
    def get(self, request):
        data = admin_dashboard_data(_days(request))
        return Response(
            {
                "days": data["days"],
                "kpis": plain(data["kpis"]),
                "category_count": data["category_count"],
                "sales_trend": plain(data["sales_trend"]),
                "top_products": plain(data["top_products"]),
                "category_performance": plain(data["category_performance"]),
                "recent_orders": OrderSummarySerializer(data["recent_orders"], many=True).data,
                "pending_vendors": [
                    {"id": v.pk, "business_name": v.business_name, "email": v.user.email, "created_at": v.created_at}
                    for v in data["pending_vendor_list"]
                ],
                "low_stock_products": [
                    {"id": p.pk, "name": p.name, "slug": p.slug, "stock": p.stock,
                     "vendor": p.vendor.business_name if p.vendor else None}
                    for p in data["low_stock_products"]
                ],
            }
        )


class VendorDashboardView(VendorScopedMixin, APIView):
    """The signed-in vendor's KPIs, sales trend and best sellers."""

    @extend_schema(parameters=[DAYS_PARAM], responses=DASHBOARD_RESPONSE)
    def get(self, request):
        data = vendor_dashboard_data(self.vendor, _days(request))
        return Response(
            {
                "days": data["days"],
                "commission_rate": plain(self.vendor.commission_rate),
                "kpis": plain(data["kpis"]),
                "sales_trend": plain(data["sales_trend"]),
                "best_sellers": plain(data["best_sellers"]),
            }
        )
