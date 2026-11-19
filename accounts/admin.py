from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from core.emails import send_templated_email

from .models import CustomerProfile, CustomUser, VendorProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "role", "is_active", "is_staff", "created_at"]
    list_filter = ["role", "is_active", "is_staff", "is_superuser", "created_at"]
    search_fields = ["username", "email", "phone", "first_name", "last_name"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at", "last_login", "date_joined"]
    fieldsets = UserAdmin.fieldsets + (
        ("Marketplace", {"fields": ("role", "phone", "avatar")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (("Marketplace", {"fields": ("role", "email", "phone")}),)
    actions = ["activate_accounts", "deactivate_accounts"]

    @admin.action(description="Activate selected accounts")
    def activate_accounts(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} account(s) activated.")

    @admin.action(description="Deactivate selected accounts")
    def deactivate_accounts(self, request, queryset):
        updated = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"{updated} account(s) deactivated. You cannot deactivate yourself.")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "city", "country", "newsletter_subscribed", "created_at"]
    list_filter = ["newsletter_subscribed", "email_notifications", "country"]
    search_fields = ["user__username", "user__email", "city", "state"]
    list_select_related = ["user"]
    raw_id_fields = ["user"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ["business_name", "user", "approval_status", "commission_rate", "business_city", "created_at"]
    list_filter = ["approval_status", "business_country", "created_at"]
    search_fields = ["business_name", "user__username", "user__email", "business_email", "store_slug"]
    list_select_related = ["user"]
    raw_id_fields = ["user"]
    readonly_fields = ["created_at", "updated_at", "approved_at", "approved_by"]
    ordering = ["-created_at"]
    fieldsets = (
        ("Account & approval", {"fields": ("user", "approval_status", "rejection_reason", "approved_at", "approved_by")}),
        ("Business", {"fields": ("business_name", "store_slug", "business_description", "business_logo",
                                 "business_banner")}),
        ("Contact", {"fields": ("business_email", "business_phone", "business_address", "business_city",
                                "business_state", "business_zip_code", "business_country")}),
        ("Registration", {"fields": ("tax_id", "business_registration_number")}),
        ("Platform settings", {"fields": ("commission_rate",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ["approve_vendors", "reject_vendors", "suspend_vendors"]

    def _notify(self, vendor):
        send_templated_email("vendor_status", {"vendor": vendor}, [vendor.business_email or vendor.user.email])

    @admin.action(description="Approve selected vendors")
    def approve_vendors(self, request, queryset):
        count = 0
        for vendor in queryset.select_related("user"):
            vendor.approve(by=request.user)
            self._notify(vendor)
            count += 1
        self.message_user(request, f"{count} vendor(s) approved.", messages.SUCCESS)

    @admin.action(description="Reject selected vendors")
    def reject_vendors(self, request, queryset):
        count = 0
        for vendor in queryset.exclude(approval_status="approved").select_related("user"):
            vendor.reject(by=request.user, reason=vendor.rejection_reason)
            self._notify(vendor)
            count += 1
        self.message_user(request, f"{count} vendor(s) rejected. Approved vendors must be suspended instead.")

    @admin.action(description="Suspend selected vendors")
    def suspend_vendors(self, request, queryset):
        count = 0
        for vendor in queryset.select_related("user"):
            vendor.suspend(by=request.user, reason=vendor.rejection_reason)
            self._notify(vendor)
            count += 1
        self.message_user(request, f"{count} vendor(s) suspended. Their products are hidden from the store.")

    def save_model(self, request, obj, form, change):
        """Keep approval metadata consistent when the status is edited directly."""
        if change and "approval_status" in form.changed_data:
            if obj.approval_status == VendorProfile.Approval.APPROVED:
                obj.approve(by=request.user)
            elif obj.approval_status == VendorProfile.Approval.REJECTED:
                obj.reject(by=request.user, reason=obj.rejection_reason)
            elif obj.approval_status == VendorProfile.Approval.SUSPENDED:
                obj.suspend(by=request.user, reason=obj.rejection_reason)
            super().save_model(request, obj, form, change)
            self._notify(obj)
            return
        super().save_model(request, obj, form, change)
