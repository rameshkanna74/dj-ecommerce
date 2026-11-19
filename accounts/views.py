from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from cart.services import CartError, add_to_cart
from core.utils import safe_redirect_target
from orders.models import Order
from products.models import Product

from .forms import (
    CustomerProfileForm,
    CustomerRegistrationForm,
    LoginForm,
    UserUpdateForm,
    VendorProfileForm,
    VendorRegistrationForm,
)
from .models import VendorProfile, Wishlist
from .permissions import customer_required, vendor_required

AUTH_BACKEND = "accounts.backends.UsernameOrEmailBackend"


# --------------------------------------------------------------------------
# Registration & authentication
# --------------------------------------------------------------------------
def register_choice(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    return render(request, "accounts/register_choice.html")


def _register(request, form_class, template, success_message, success_url):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend=AUTH_BACKEND)
        messages.success(request, success_message)
        return redirect(success_url)
    return render(request, template, {"form": form})


def customer_register(request):
    return _register(
        request,
        CustomerRegistrationForm,
        "accounts/customer_register.html",
        "Welcome to CoreCart! Your account has been created.",
        "core:home",
    )


def vendor_register(request):
    return _register(
        request,
        VendorRegistrationForm,
        "accounts/vendor_register.html",
        "Your vendor application has been received. We'll email you once it has been reviewed.",
        "accounts:vendor_pending",
    )


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    """POST-only logout (Django's LogoutView rejects GET)."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "You have been signed out.")
        return response


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


# --------------------------------------------------------------------------
# Dashboards & profiles
# --------------------------------------------------------------------------
@login_required
def dashboard(request):
    user = request.user
    if user.is_platform_admin:
        return redirect("analytics:admin_dashboard")
    if user.is_vendor:
        profile = getattr(user, "vendor_profile", None)
        if profile is not None and profile.can_sell:
            return redirect("accounts:vendor_dashboard")
        return redirect("accounts:vendor_pending")
    if user.is_customer:
        return redirect("accounts:customer_dashboard")
    return redirect("core:home")


@login_required
def profile(request):
    if request.user.is_customer:
        return redirect("accounts:customer_profile")
    if request.user.is_vendor:
        return redirect("accounts:vendor_profile")
    return redirect("accounts:password_change")


@customer_required
def customer_dashboard(request):
    orders = Order.objects.filter(user=request.user)
    stats = orders.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status__in=["pending", "processing", "shipped"])),
    )
    wishlist_count = Wishlist.objects.filter(user=request.user).aggregate(n=Count("products"))["n"] or 0
    return render(
        request,
        "accounts/customer_dashboard.html",
        {
            "recent_orders": orders.prefetch_related("items")[:5],
            "total_orders": stats["total"],
            "active_orders": stats["active"],
            "wishlist_count": wishlist_count,
            "open_tickets": request.user.tickets.exclude(status="closed").count(),
        },
    )


@customer_required
def customer_profile(request):
    profile = request.user.customer_profile
    user_form = UserUpdateForm(request.POST or None, request.FILES or None, instance=request.user)
    profile_form = CustomerProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("accounts:customer_profile")
    return render(request, "accounts/customer_profile.html", {"user_form": user_form, "profile_form": profile_form})


@login_required
def vendor_pending(request):
    if not request.user.is_vendor or not hasattr(request.user, "vendor_profile"):
        messages.error(request, "This page is only for vendor accounts.")
        return redirect("core:home")
    vendor = request.user.vendor_profile
    if vendor.can_sell:
        return redirect("accounts:vendor_dashboard")
    return render(request, "accounts/vendor_pending.html", {"vendor_profile": vendor})


@vendor_required
def vendor_dashboard(request):
    from analytics.services import vendor_dashboard_data

    vendor = request.user.vendor_profile
    return render(request, "accounts/vendor_dashboard.html", {"vendor": vendor, **vendor_dashboard_data(vendor)})


@vendor_required
def vendor_profile(request):
    vendor = request.user.vendor_profile
    user_form = UserUpdateForm(request.POST or None, request.FILES or None, instance=request.user)
    profile_form = VendorProfileForm(request.POST or None, request.FILES or None, instance=vendor)
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, "Store settings saved.")
        return redirect("accounts:vendor_profile")
    return render(
        request,
        "accounts/vendor_profile.html",
        {"user_form": user_form, "profile_form": profile_form, "vendor": vendor},
    )


def vendor_store(request, slug):
    vendor = get_object_or_404(
        VendorProfile.objects.select_related("user"), store_slug=slug, approval_status="approved", user__is_active=True
    )
    products = Product.objects.visible().filter(vendor=vendor).for_listing().prefetch_related("variants")
    page = Paginator(products, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/vendor_store.html",
        {"vendor": vendor, "page_obj": page, "products": page.object_list, "product_count": page.paginator.count},
    )


# --------------------------------------------------------------------------
# Wishlist
# --------------------------------------------------------------------------
@customer_required
def wishlist_view(request):
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    products = wishlist.products.for_listing().prefetch_related("variants")
    return render(request, "accounts/wishlist.html", {"products": products})


@require_POST
@customer_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product.objects.visible(), pk=product_id)
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    if wishlist.products.filter(pk=product.pk).exists():
        wishlist.products.remove(product)
        messages.info(request, f'"{product.name}" removed from your wishlist.')
    else:
        wishlist.products.add(product)
        messages.success(request, f'"{product.name}" saved to your wishlist.')
    return redirect(safe_redirect_target(request, request.POST.get("next"), product.get_absolute_url()))


@require_POST
@customer_required
def wishlist_move_to_cart(request, product_id):
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    product = get_object_or_404(wishlist.products.all(), pk=product_id)
    if product.has_variants:
        messages.info(request, f'Choose an option for "{product.name}" to add it to your cart.')
        return redirect(product.get_absolute_url())
    try:
        add_to_cart(request.user, product, 1)
    except CartError as exc:
        messages.error(request, str(exc))
        return redirect("accounts:wishlist")
    wishlist.products.remove(product)
    messages.success(request, f'"{product.name}" moved to your cart.')
    return redirect("accounts:wishlist")
