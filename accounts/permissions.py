"""
Role-based access control for function-based and class-based views.

Role information always comes from the authenticated user record, never from
request data.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def _check_customer(request):
    if not request.user.is_customer:
        raise PermissionDenied("This page is only available to customer accounts.")
    return None


def _check_approved_vendor(request):
    user = request.user
    if not user.is_vendor:
        raise PermissionDenied("This page is only available to vendor accounts.")
    profile = getattr(user, "vendor_profile", None)
    if profile is None:
        raise PermissionDenied("Vendor profile not found.")
    if not profile.can_sell:
        messages.warning(request, f"Your vendor account is {profile.get_approval_status_display().lower()}.")
        return redirect("accounts:vendor_pending")
    return None


def _check_platform_admin(request):
    if not request.user.is_platform_admin:
        raise PermissionDenied("This page is only available to administrators.")
    return None


def _make_decorator(check):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            response = check(request)
            if response is not None:
                return response
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


customer_required = _make_decorator(_check_customer)
vendor_required = _make_decorator(_check_approved_vendor)
admin_required = _make_decorator(_check_platform_admin)


class _RoleRequiredMixin(AccessMixin):
    role_check = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        response = type(self).role_check(request)
        if response is not None:
            return response
        return super().dispatch(request, *args, **kwargs)


class CustomerRequiredMixin(_RoleRequiredMixin):
    role_check = staticmethod(_check_customer)


class VendorRequiredMixin(_RoleRequiredMixin):
    """Approved, active vendors only. Exposes ``self.vendor`` to the view."""

    role_check = staticmethod(_check_approved_vendor)

    @property
    def vendor(self):
        return self.request.user.vendor_profile


class PlatformAdminRequiredMixin(_RoleRequiredMixin):
    role_check = staticmethod(_check_platform_admin)
