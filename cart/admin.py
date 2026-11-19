from django.contrib import admin

from .models import CartItem


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "variant", "quantity", "is_saved_for_later", "updated_at"]
    list_filter = ["is_saved_for_later"]
    search_fields = ["user__username", "user__email", "product__name"]
    list_select_related = ["user", "product", "variant"]
    raw_id_fields = ["user", "product", "variant"]
