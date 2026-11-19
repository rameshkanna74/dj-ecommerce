from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.permissions import IsCustomer
from products.api.serializers import ProductListSerializer
from products.models import Product, ProductVariant

from . import services
from .models import CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    variant = serializers.SerializerMethodField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    available_stock = serializers.IntegerField(read_only=True)
    problem = serializers.CharField(read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "variant", "quantity", "is_saved_for_later", "unit_price", "subtotal",
                  "available_stock", "problem", "created_at", "updated_at"]

    def get_variant(self, obj) -> dict | None:
        if not obj.variant_id:
            return None
        return {"id": obj.variant_id, "label": obj.variant.label}


class CartSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    saved_items = CartItemSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_quantity = serializers.IntegerField()
    has_problems = serializers.BooleanField()


class CartAddSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    variant = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(default=1)


class CartItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(required=False)
    is_saved_for_later = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide quantity and/or is_saved_for_later.")
        return attrs


def _cart_response(request, status_code=status.HTTP_200_OK):
    summary = services.get_cart_summary(request.user)
    return Response(CartSerializer(summary, context={"request": request}).data, status=status_code)


class CartView(APIView):
    """The customer's cart. Every amount is recalculated from current database prices."""

    permission_classes = [IsCustomer]

    @extend_schema(responses=CartSerializer)
    def get(self, request):
        return _cart_response(request)


class CartItemsView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(request=CartAddSerializer, responses={201: CartSerializer})
    def post(self, request):
        """Add a product (adding an existing line increases its quantity)."""
        serializer = CartAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        product = get_object_or_404(Product.objects.visible().prefetch_related("variants"), pk=data["product"])
        variant = None
        if data.get("variant"):
            variant = get_object_or_404(ProductVariant, pk=data["variant"], product=product)
        services.add_to_cart(request.user, product, data["quantity"], variant)
        return _cart_response(request, status.HTTP_201_CREATED)


class CartItemView(APIView):
    permission_classes = [IsCustomer]

    def _item(self, request, pk):
        return get_object_or_404(
            CartItem.objects.select_related("product__category", "product__vendor__user", "variant"),
            pk=pk,
            user=request.user,
        )

    @extend_schema(request=CartItemUpdateSerializer, responses=CartSerializer)
    def patch(self, request, pk):
        """Change the quantity and/or move the line to or from "saved for later"."""
        item = self._item(request, pk)
        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "is_saved_for_later" in data and data["is_saved_for_later"] != item.is_saved_for_later:
            services.set_saved_for_later(item, data["is_saved_for_later"])
        if "quantity" in data:
            services.update_quantity(item, data["quantity"])
        return _cart_response(request)

    @extend_schema(responses=CartSerializer)
    def delete(self, request, pk):
        self._item(request, pk).delete()
        return _cart_response(request)
