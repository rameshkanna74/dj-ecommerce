"""Role-based API permissions. Roles always come from the authenticated user record."""

from rest_framework.permissions import BasePermission


class IsCustomer(BasePermission):
    message = "This endpoint is only available to customer accounts."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_customer)


class IsVendor(BasePermission):
    """Any vendor account, approved or not (e.g. to read application status)."""

    message = "This endpoint is only available to vendor accounts."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_vendor and hasattr(user, "vendor_profile"))


class IsApprovedVendor(BasePermission):
    message = "Your vendor account must be approved and active to use this endpoint."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.approved_vendor_profile is not None)


class IsPlatformAdmin(BasePermission):
    message = "This endpoint is only available to administrators."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_platform_admin)


def is_schema_generation(view):
    """drf-spectacular introspects views with an anonymous user; querysets must not touch it."""
    return getattr(view, "swagger_fake_view", False)


class VendorScopedMixin:
    """Gives API views ``self.vendor`` for the signed-in approved vendor."""

    permission_classes = [IsApprovedVendor]

    @property
    def vendor(self):
        return self.request.user.vendor_profile
