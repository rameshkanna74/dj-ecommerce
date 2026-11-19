from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import SupportTicket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    fields = ["created_at", "author", "is_staff_reply", "status_change", "body"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ["id", "subject", "user", "status", "order", "updated_at", "respond_link"]
    list_filter = ["status", "created_at"]
    search_fields = ["subject", "message", "user__username", "user__email"]
    list_select_related = ["user", "order"]
    raw_id_fields = ["user", "order"]
    inlines = [TicketMessageInline]

    @admin.display(description="")
    def respond_link(self, obj):
        return format_html('<a href="{}">Respond</a>', reverse("support:staff_ticket_detail", args=[obj.pk]))
