from django.contrib import admin, messages
from django.db.models import ProtectedError

from .models import Category, Product, ProductImage, ProductQuestion, ProductVariant, Review, StockAlert


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "product_total", "created_at"]
    list_filter = ["is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]

    @admin.display(description="Products")
    def product_total(self, obj):
        return obj.products.count()

    def delete_queryset(self, request, queryset):
        try:
            super().delete_queryset(request, queryset)
        except ProtectedError:
            self.message_user(
                request, "Categories that still contain products cannot be deleted. Deactivate them instead.",
                messages.ERROR,
            )


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "vendor", "category", "price", "stock", "is_active", "is_featured", "average_rating",
                    "created_at"]
    list_filter = ["is_active", "is_featured", "category", "vendor__approval_status", "created_at"]
    list_editable = ["price", "stock", "is_active", "is_featured"]
    list_select_related = ["vendor", "category"]
    search_fields = ["name", "description", "vendor__business_name"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["average_rating", "review_count", "created_at", "updated_at"]
    raw_id_fields = ["vendor"]
    date_hierarchy = "created_at"
    inlines = [ProductVariantInline, ProductImageInline]
    actions = ["mark_featured", "unmark_featured"]

    @admin.action(description="Feature on homepage")
    def mark_featured(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_featured=True)} product(s) featured.")

    @admin.action(description="Remove from homepage features")
    def unmark_featured(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_featured=False)} product(s) un-featured.")


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "created_at", "notified_at"]
    list_filter = ["notified_at"]
    list_select_related = ["product", "user"]
    search_fields = ["product__name", "user__email"]
    raw_id_fields = ["product", "user"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "rating", "is_verified_purchase", "is_visible", "created_at"]
    list_filter = ["is_visible", "rating", "is_verified_purchase"]
    list_editable = ["is_visible"]
    list_select_related = ["product", "user"]
    search_fields = ["product__name", "user__username", "comment"]
    raw_id_fields = ["product", "user"]
    actions = ["hide_reviews", "show_reviews"]

    @admin.action(description="Hide selected reviews")
    def hide_reviews(self, request, queryset):
        for review in queryset:
            review.is_visible = False
            review.save(update_fields=["is_visible", "updated_at"])  # triggers rating refresh

    @admin.action(description="Show selected reviews")
    def show_reviews(self, request, queryset):
        for review in queryset:
            review.is_visible = True
            review.save(update_fields=["is_visible", "updated_at"])


@admin.register(ProductQuestion)
class ProductQuestionAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "is_answered", "is_public", "created_at"]
    list_filter = ["is_answered", "is_public"]
    list_editable = ["is_public"]
    list_select_related = ["product", "user"]
    search_fields = ["product__name", "question", "answer"]
    raw_id_fields = ["product", "user", "answered_by"]
