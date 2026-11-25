from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from core.ratelimit import ratelimit_post

from . import views

app_name = "accounts"

urlpatterns = [
    # Registration & authentication
    path("accounts/register/", views.register_choice, name="register"),
    path("accounts/register/customer/", views.customer_register, name="customer_register"),
    path("accounts/register/vendor/", views.vendor_register, name="vendor_register"),
    path("accounts/login/", views.LoginView.as_view(), name="login"),
    path("accounts/logout/", views.LogoutView.as_view(), name="logout"),
    path("accounts/password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path("accounts/password/change/done/", views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path(
        "accounts/password-reset/",
        ratelimit_post("password-reset", limit=10, window=60 * 60)(auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="emails/password_reset_body.txt",
            subject_template_name="emails/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        )),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "accounts/password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    # Customer area
    path("accounts/dashboard/", views.dashboard, name="dashboard"),
    path("accounts/dashboard/customer/", views.customer_dashboard, name="customer_dashboard"),
    path("accounts/profile/", views.profile, name="profile"),
    path("accounts/profile/customer/", views.customer_profile, name="customer_profile"),
    path("accounts/wishlist/", views.wishlist_view, name="wishlist"),
    path("accounts/wishlist/<int:product_id>/toggle/", views.toggle_wishlist, name="toggle_wishlist"),
    path("accounts/wishlist/<int:product_id>/move-to-cart/", views.wishlist_move_to_cart, name="wishlist_move_to_cart"),
    # Vendor area
    path("vendor/", views.vendor_dashboard, name="vendor_dashboard"),
    path("vendor/pending/", views.vendor_pending, name="vendor_pending"),
    path("vendor/store-settings/", views.vendor_profile, name="vendor_profile"),
    # Public storefronts
    path("store/<slug:slug>/", views.vendor_store, name="vendor_store"),
]
