from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("staff/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("staff/reports/orders.csv", views.export_orders, name="export_orders"),
    path("staff/reports/products.csv", views.export_products, name="export_products"),
    path("vendor/analytics/", views.vendor_analytics, name="vendor_dashboard"),
    path("vendor/analytics/sales.csv", views.vendor_export_sales, name="vendor_export_sales"),
]
