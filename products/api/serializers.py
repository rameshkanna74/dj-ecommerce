from decimal import Decimal

from rest_framework import serializers

from accounts.models import VendorProfile
from products.models import Category, Product, ProductImage, ProductQuestion, ProductVariant, Review


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, help_text="Number of products shoppers can see")

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "product_count"]


class CategoryRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class VendorRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProfile
        fields = ["id", "business_name", "store_slug"]


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProfile
        fields = ["id", "business_name", "store_slug", "business_description", "business_logo", "business_banner",
                  "business_city", "business_country"]


class VariantSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(source="current_price", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = ProductVariant
        fields = ["id", "attribute_name", "attribute_value", "label", "price", "price_override", "stock", "is_active"]
        read_only_fields = ["id", "label", "price"]

    def validate(self, attrs):
        product = self.context.get("product") or getattr(self.instance, "product", None)
        name = attrs.get("attribute_name", getattr(self.instance, "attribute_name", None))
        value = attrs.get("attribute_value", getattr(self.instance, "attribute_value", None))
        duplicates = ProductVariant.objects.filter(product=product, attribute_name=name, attribute_value=value)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if product is not None and duplicates.exists():
            raise serializers.ValidationError("This option already exists for the product.")
        return attrs


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "position"]


class ProductListSerializer(serializers.ModelSerializer):
    category = CategoryRefSerializer(read_only=True)
    vendor = VendorRefSerializer(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    has_variants = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "price", "cover_image", "category", "vendor", "average_rating", "review_count",
                  "is_featured", "is_in_stock", "is_low_stock", "has_variants"]


class ProductDetailSerializer(ProductListSerializer):
    variants = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
    total_available_stock = serializers.IntegerField(read_only=True)
    rating_breakdown = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description", "variants", "images", "total_available_stock", "rating_breakdown", "created_at",
            "updated_at",
        ]

    def get_variants(self, obj) -> list[dict]:
        return VariantSerializer(obj.active_variants, many=True).data

    def get_rating_breakdown(self, obj) -> dict[str, int]:
        counts = {str(star): 0 for star in range(1, 6)}
        for rating in obj.reviews.filter(is_visible=True).values_list("rating", flat=True):
            counts[str(rating)] += 1
        return counts


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    product = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    rating = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = Review
        fields = ["id", "product", "rating", "comment", "author", "is_verified_purchase", "created_at", "updated_at"]
        read_only_fields = ["id", "product", "author", "is_verified_purchase", "created_at", "updated_at"]

    def get_author(self, obj) -> str:
        return obj.user.first_name or obj.user.username

    def validate_comment(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Please write at least 10 characters.")
        if len(value) > 2000:
            raise serializers.ValidationError("Reviews are limited to 2000 characters.")
        return value


class VendorReviewSerializer(ReviewSerializer):
    class Meta(ReviewSerializer.Meta):
        fields = ReviewSerializer.Meta.fields + ["is_visible"]


class QuestionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    product = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = ProductQuestion
        fields = ["id", "product", "question", "answer", "is_answered", "author", "created_at", "answered_at"]
        read_only_fields = ["id", "product", "answer", "is_answered", "author", "created_at", "answered_at"]

    def get_author(self, obj) -> str:
        return obj.user.first_name or obj.user.username

    def validate_question(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Please write a longer question.")
        return value[:1000]


class AnswerSerializer(serializers.Serializer):
    answer = serializers.CharField(max_length=2000)

    def validate_answer(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Please write an answer.")
        return value


class VendorProductSerializer(serializers.ModelSerializer):
    """Write serializer for a vendor's own products. Ownership is assigned server-side."""

    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.active())
    variants = VariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    units_sold = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "category", "description", "price", "stock", "is_active", "cover_image",
                  "is_featured", "average_rating", "review_count", "units_sold", "variants", "images", "created_at",
                  "updated_at"]
        read_only_fields = ["id", "slug", "is_featured", "average_rating", "review_count", "units_sold", "created_at",
                            "updated_at"]

    def validate_price(self, value):
        if value is None or value <= Decimal("0"):
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
