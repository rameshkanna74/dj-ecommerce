from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from . import payments, services
from .models import Coupon, Order, OrderItem, OrderTimeline


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ["product_name", "variant_label", "vendor", "quantity", "price", "status", "tracking_number", "edit_link"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="")
    def edit_link(self, obj):
        url = reverse("admin:orders_orderitem_change", args=[obj.pk])
        return format_html('<a href="{}">Update status</a>', url)


class OrderTimelineInline(admin.TabularInline):
    model = OrderTimeline
    extra = 0
    can_delete = False
    fields = ["timestamp", "status", "note", "actor"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "user", "status", "payment_status", "payment_method", "total_amount",
                    "created_at", "invoice_link"]
    list_filter = ["status", "payment_status", "payment_method", "created_at"]
    search_fields = ["order_number", "user__username", "user__email", "shipping_full_name", "tracking_number"]
    list_select_related = ["user"]
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, OrderTimelineInline]
    readonly_fields = [
        "order_number", "user", "status", "payment_status", "paid_at", "payment_reference", "payment_method",
        "subtotal_amount", "discount_amount", "total_amount", "coupon", "coupon_code", "created_at", "updated_at",
        "cancelled_at", "guest_email", "guest_name",
    ]
    fieldsets = (
        ("Order", {"fields": ("order_number", "user", "status", "created_at", "updated_at", "cancelled_at")}),
        ("Payment", {"fields": ("payment_method", "payment_status", "paid_at", "payment_reference")}),
        ("Amounts", {"fields": ("subtotal_amount", "coupon", "coupon_code", "discount_amount", "total_amount")}),
        ("Delivery", {"fields": ("shipping_full_name", "shipping_phone", "shipping_address", "shipping_city",
                                 "shipping_state", "shipping_postal_code", "shipping_country", "customer_note",
                                 "tracking_number")}),
        ("Legacy guest fields", {"fields": ("guest_email", "guest_name"), "classes": ("collapse",)}),
    )
    actions = ["mark_paid", "cancel_orders", "mark_refunded"]

    def has_add_permission(self, request):
        return False  # Orders are only created through checkout.

    def has_delete_permission(self, request, obj=None):
        return False  # Keep the financial record; cancel instead.

    @admin.display(description="Invoice")
    def invoice_link(self, obj):
        return format_html('<a href="{}" target="_blank">View</a>', reverse("orders:invoice", args=[obj.order_number]))

    @admin.action(description="Record payment received")
    def mark_paid(self, request, queryset):
        done = 0
        for order in queryset:
            try:
                payments.mark_order_paid(order, request.user)
                done += 1
            except payments.PaymentError as exc:
                self.message_user(request, f"{order.order_number}: {exc}", messages.ERROR)
        self.message_user(request, f"{done} order(s) marked as paid.")

    @admin.action(description="Record refund")
    def mark_refunded(self, request, queryset):
        for order in queryset:
            try:
                payments.mark_order_refunded(order, request.user)
            except payments.PaymentError as exc:
                self.message_user(request, f"{order.order_number}: {exc}", messages.ERROR)

    @admin.action(description="Cancel selected orders (restocks items)")
    def cancel_orders(self, request, queryset):
        done = 0
        for order in queryset:
            try:
                services.cancel_order(order, request.user, "Cancelled by administrator.")
                done += 1
            except services.OrderWorkflowError as exc:
                self.message_user(request, f"{order.order_number}: {exc}", messages.ERROR)
        self.message_user(request, f"{done} order(s) cancelled.")


class OrderItemAdminForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ["status", "tracking_number"]

    def clean(self):
        cleaned = super().clean()
        new_status = cleaned.get("status")
        original = OrderItem.objects.get(pk=self.instance.pk).status if self.instance.pk else None
        if original and new_status != original and new_status not in OrderItem.ALLOWED_TRANSITIONS[original]:
            raise forms.ValidationError(f"Cannot move this item from {original} to {new_status}.")
        return cleaned


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    form = OrderItemAdminForm
    list_display = ["order", "product_name", "vendor", "quantity", "price", "status", "tracking_number"]
    list_filter = ["status", "vendor"]
    search_fields = ["order__order_number", "product_name", "tracking_number"]
    list_select_related = ["order", "vendor"]
    readonly_fields = ["order", "product", "variant", "vendor", "product_name", "variant_label", "quantity", "price",
                       "commission_rate"]
    fields = readonly_fields + ["status", "tracking_number"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        """Route status changes through the workflow service (restock, timeline, parent status)."""
        original = OrderItem.objects.get(pk=obj.pk)
        if obj.status != original.status:
            new_status, tracking = obj.status, obj.tracking_number
            try:
                services.set_item_status(original, new_status, request.user, tracking)
            except services.OrderWorkflowError as exc:
                self.message_user(request, str(exc), messages.ERROR)
        elif "tracking_number" in form.changed_data:
            OrderItem.objects.filter(pk=obj.pk).update(tracking_number=obj.tracking_number)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "discount_type", "value", "min_order_amount", "active", "valid_from", "valid_to",
                    "used_count", "usage_limit"]
    list_filter = ["active", "discount_type"]
    search_fields = ["code", "description"]
    readonly_fields = ["used_count"]
