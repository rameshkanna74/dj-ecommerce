from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/coupon/", views.apply_coupon, name="apply_coupon"),
    path("checkout/coupon/remove/", views.remove_coupon, name="remove_coupon"),
    path("orders/", views.OrderListView.as_view(), name="list"),
    path("orders/<str:order_number>/", views.order_detail, name="detail"),
    path("orders/<str:order_number>/invoice/", views.invoice_view, name="invoice"),
    path("orders/<str:order_number>/cancel/", views.cancel_order, name="cancel"),
    # Vendor fulfilment
    path("vendor/orders/", views.VendorOrderListView.as_view(), name="vendor_order_list"),
    path("vendor/orders/<str:order_number>/", views.vendor_order_detail, name="vendor_order_detail"),
    path("vendor/order-items/<int:pk>/status/", views.vendor_update_item, name="vendor_update_item"),
]
