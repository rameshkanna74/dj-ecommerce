"""REST API v1, mounted at /api/v1/."""

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.urls import include, path
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenVerifyView

from accounts.api import views as account_views
from analytics.api import AdminDashboardView, VendorDashboardView
from cart.api import CartItemsView, CartItemView, CartView
from core.api import staff
from orders import api as order_api
from products.api import views as product_views
from support.api import StaffTicketViewSet, TicketViewSet


@extend_schema(responses={200: {"type": "object", "properties": {"status": {"type": "string"},
                                                                   "version": {"type": "string"}}}})
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@throttle_classes([])
def health(request):
    """Liveness/readiness probe: checks the database and cache connections."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    cache.set("health:ping", "1", 5)
    if cache.get("health:ping") != "1":
        return Response({"status": "degraded", "version": settings.CORECART_VERSION}, status=503)
    return Response({"status": "ok", "version": settings.CORECART_VERSION})


router = DefaultRouter()
router.include_root_view = False
router.register("categories", product_views.CategoryViewSet, basename="category")
router.register("products", product_views.ProductViewSet, basename="product")
router.register("reviews", product_views.ReviewViewSet, basename="review")
router.register("stores", product_views.StoreViewSet, basename="store")
router.register("support/tickets", TicketViewSet, basename="ticket")
router.register("vendor/products", product_views.VendorProductViewSet, basename="vendor-product")
router.register("vendor/reviews", product_views.VendorReviewViewSet, basename="vendor-review")
router.register("vendor/questions", product_views.VendorQuestionViewSet, basename="vendor-question")
router.register("staff/vendors", staff.StaffVendorViewSet, basename="staff-vendor")
router.register("staff/orders", staff.StaffOrderViewSet, basename="staff-order")
router.register("staff/coupons", staff.StaffCouponViewSet, basename="staff-coupon")
router.register("staff/categories", staff.StaffCategoryViewSet, basename="staff-category")
router.register("staff/users", staff.StaffUserViewSet, basename="staff-user")
router.register("staff/products", staff.StaffProductViewSet, basename="staff-product")
router.register("staff/reviews", staff.StaffReviewViewSet, basename="staff-review")
router.register("staff/tickets", StaffTicketViewSet, basename="staff-ticket")

child_list = {"get": "list", "post": "create"}
child_detail = {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}

app_name = "api"

urlpatterns = [
    path("health/", health, name="health"),
    # Auth
    path("auth/register/customer/", account_views.CustomerRegisterView.as_view(), name="register-customer"),
    path("auth/register/vendor/", account_views.VendorRegisterView.as_view(), name="register-vendor"),
    path("auth/token/", account_views.LoginView.as_view(), name="token"),
    path("auth/token/refresh/", account_views.RefreshView.as_view(), name="token-refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("auth/logout/", account_views.LogoutView.as_view(), name="logout"),
    path("auth/password/change/", account_views.PasswordChangeView.as_view(), name="password-change"),
    path("auth/password/reset/", account_views.PasswordResetRequestView.as_view(), name="password-reset"),
    path("auth/password/reset/confirm/", account_views.PasswordResetConfirmView.as_view(),
         name="password-reset-confirm"),
    path("me/", account_views.MeView.as_view(), name="me"),
    # Customer
    path("wishlist/", account_views.WishlistView.as_view(), name="wishlist"),
    path("wishlist/<int:product_id>/", account_views.WishlistItemView.as_view(), name="wishlist-item"),
    path("wishlist/<int:product_id>/move-to-cart/", account_views.WishlistMoveToCartView.as_view(),
         name="wishlist-move"),
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/items/", CartItemsView.as_view(), name="cart-items"),
    path("cart/items/<int:pk>/", CartItemView.as_view(), name="cart-item"),
    path("checkout/payment-methods/", order_api.PaymentMethodsView.as_view(), name="payment-methods"),
    path("checkout/preview/", order_api.CheckoutPreviewView.as_view(), name="checkout-preview"),
    path("checkout/", order_api.CheckoutView.as_view(), name="checkout"),
    path("orders/", order_api.OrderListView.as_view(), name="orders"),
    path("orders/<str:order_number>/", order_api.OrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:order_number>/cancel/", order_api.OrderCancelView.as_view(), name="order-cancel"),
    # Vendor
    path("vendor/application/", account_views.VendorApplicationView.as_view(), name="vendor-application"),
    path("vendor/dashboard/", VendorDashboardView.as_view(), name="vendor-dashboard"),
    path("vendor/products/<int:product_pk>/variants/",
         product_views.VendorVariantViewSet.as_view(child_list), name="vendor-variant-list"),
    path("vendor/products/<int:product_pk>/variants/<int:pk>/",
         product_views.VendorVariantViewSet.as_view(child_detail), name="vendor-variant-detail"),
    path("vendor/products/<int:product_pk>/images/",
         product_views.VendorProductImageViewSet.as_view(child_list), name="vendor-image-list"),
    path("vendor/products/<int:product_pk>/images/<int:pk>/",
         product_views.VendorProductImageViewSet.as_view(child_detail), name="vendor-image-detail"),
    path("vendor/order-items/", order_api.VendorOrderItemListView.as_view(), name="vendor-order-items"),
    path("vendor/order-items/<int:pk>/status/", order_api.VendorOrderItemStatusView.as_view(),
         name="vendor-order-item-status"),
    path("vendor/orders/<str:order_number>/", order_api.VendorOrderDetailView.as_view(), name="vendor-order-detail"),
    # Staff
    path("staff/dashboard/", AdminDashboardView.as_view(), name="staff-dashboard"),
    path("staff/order-items/<int:pk>/status/", staff.StaffOrderItemStatusView.as_view(),
         name="staff-order-item-status"),
    path("", include(router.urls)),
    # Documentation
    path("schema/", SpectacularAPIView.as_view(permission_classes=[permissions.AllowAny]), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema", permission_classes=[permissions.AllowAny]),
         name="docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api:schema", permission_classes=[permissions.AllowAny]),
         name="redoc"),
]
