from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomerProfile
from cart.api import CartItemSerializer
from core.api.permissions import IsCustomer, VendorScopedMixin

from . import services
from .models import Order, OrderItem, OrderTimeline
from .payments import available_payment_methods, payment_instructions

# --------------------------------------------------------------------------
# Serializers
# --------------------------------------------------------------------------


class ShippingSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    phone = serializers.RegexField(r"^\+?[0-9 ()\-]{7,20}$", max_length=20,
                                   error_messages={"invalid": "Enter a valid phone number."})
    address = serializers.CharField(max_length=500)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100)

    def validate_full_name(self, value):
        return " ".join(value.split())


class CheckoutSerializer(ShippingSerializer):
    payment_method = serializers.ChoiceField(choices=[])
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    customer_note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    save_address = serializers.BooleanField(required=False, default=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].choices = available_payment_methods()

    def shipping(self):
        return {key: self.validated_data[key] for key in ShippingSerializer().fields}


class CheckoutPreviewRequestSerializer(serializers.Serializer):
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")


class CheckoutPreviewSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    coupon_code = serializers.SerializerMethodField()
    coupon_error = serializers.CharField()
    problems = serializers.ListField(child=serializers.CharField())

    def get_coupon_code(self, obj) -> str | None:
        return obj.coupon.code if obj.coupon else None


class OrderItemSerializer(serializers.ModelSerializer):
    vendor = serializers.SerializerMethodField()
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_slug", "product_name", "variant", "variant_label", "vendor", "quantity",
                  "price", "subtotal", "status", "status_display", "tracking_number", "updated_at"]

    def get_vendor(self, obj) -> dict | None:
        if not obj.vendor_id:
            return None
        return {"id": obj.vendor_id, "business_name": obj.vendor.business_name, "store_slug": obj.vendor.store_slug}


class TimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTimeline
        fields = ["id", "status", "note", "timestamp"]


class OrderSummarySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    item_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Order
        fields = ["order_number", "status", "status_display", "payment_status", "payment_status_display",
                  "payment_method", "subtotal_amount", "discount_amount", "total_amount", "item_count", "created_at"]


class ShippingAddressSerializer(serializers.Serializer):
    full_name = serializers.CharField(source="shipping_full_name")
    phone = serializers.CharField(source="shipping_phone")
    address = serializers.CharField(source="shipping_address")
    city = serializers.CharField(source="shipping_city")
    state = serializers.CharField(source="shipping_state")
    postal_code = serializers.CharField(source="shipping_postal_code")
    country = serializers.CharField(source="shipping_country")


class OrderDetailSerializer(OrderSummarySerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = TimelineSerializer(many=True, read_only=True)
    shipping_address = ShippingAddressSerializer(source="*", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)
    payment_instructions = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta(OrderSummarySerializer.Meta):
        fields = OrderSummarySerializer.Meta.fields + [
            "payment_method_display", "payment_instructions", "paid_at", "coupon_code", "shipping_address",
            "customer_note", "tracking_number", "cancelled_at", "updated_at", "can_cancel", "items", "timeline",
        ]

    def get_payment_instructions(self, obj) -> str:
        return "" if obj.is_paid or obj.is_cancelled else payment_instructions(obj)

    def get_can_cancel(self, obj) -> bool:
        return obj.can_customer_cancel()


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class ItemStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderItem.Status.choices)
    tracking_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


def order_detail_queryset():
    return Order.objects.select_related("coupon").prefetch_related(
        Prefetch("items", queryset=OrderItem.objects.select_related("product", "vendor")), "timeline"
    )


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------
class PaymentMethodsView(APIView):
    @extend_schema(responses={200: {"type": "array", "items": {"type": "object"}}})
    def get(self, request):
        return Response([{"value": v, "label": label} for v, label in available_payment_methods()])


class CheckoutPreviewView(APIView):
    """Totals for the active cart with an optional coupon. No side effects."""

    permission_classes = [IsCustomer]

    @extend_schema(request=CheckoutPreviewRequestSerializer, responses=CheckoutPreviewSerializer)
    def post(self, request):
        serializer = CheckoutPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        summary = services.build_checkout_summary(request.user, serializer.validated_data["coupon_code"])
        return Response(CheckoutPreviewSerializer(summary, context={"request": request}).data)


IDEMPOTENCY_PARAM = OpenApiParameter(
    "Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
    description="Unique key per checkout attempt (e.g. a UUID). Retrying with the same key returns the same order.",
)


class CheckoutView(APIView):
    """
    Place an order from the active cart. Returns 201 for a new order and 200 when the
    ``Idempotency-Key`` was already used (the original order is returned).
    Orders are created unpaid; payment is confirmed by an administrator.
    """

    permission_classes = [IsCustomer]

    @extend_schema(request=CheckoutSerializer, parameters=[IDEMPOTENCY_PARAM],
                   responses={201: OrderDetailSerializer, 200: OrderDetailSerializer})
    def post(self, request):
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 64:
            return Response({"detail": "An Idempotency-Key header (max 64 chars) is required.",
                             "code": "idempotency_key_required"}, status=status.HTTP_400_BAD_REQUEST)
        existing = Order.objects.filter(checkout_token=key, user=request.user).first()
        if existing is None and Order.objects.filter(checkout_token=key).exists():
            return Response({"detail": "This Idempotency-Key was already used.", "code": "idempotency_key_reused"},
                            status=status.HTTP_409_CONFLICT)
        if existing is not None:
            return Response(OrderDetailSerializer(order_detail_queryset().get(pk=existing.pk)).data)

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order, created = services.place_order(
            request.user,
            shipping=serializer.shipping(),
            payment_method=data["payment_method"],
            coupon_code=data["coupon_code"],
            checkout_token=key,
            customer_note=data["customer_note"],
        )
        if created and data["save_address"]:
            CustomerProfile.objects.filter(user=request.user).update(
                address=data["address"], city=data["city"], state=data["state"], zip_code=data["postal_code"],
                country=data["country"],
            )
        return Response(OrderDetailSerializer(order_detail_queryset().get(pk=order.pk)).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# --------------------------------------------------------------------------
# Customer orders
# --------------------------------------------------------------------------
class OrderListView(generics.ListAPIView):
    serializer_class = OrderSummarySerializer
    permission_classes = [IsCustomer]

    @extend_schema(parameters=[OpenApiParameter("status", str, enum=Order.Status.values)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Order.objects.filter(user=self.request.user).annotate(item_count=Count("items"))
        status_filter = self.request.query_params.get("status")
        if status_filter in Order.Status.values:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by("-created_at")


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [IsCustomer]
    lookup_field = "order_number"

    def get_queryset(self):
        return order_detail_queryset().filter(user=self.request.user)


class OrderCancelView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(request=CancelSerializer, responses=OrderDetailSerializer)
    def post(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number, user=request.user)
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not order.can_customer_cancel():
            return Response({"detail": "This order can no longer be cancelled.", "code": "not_cancellable"},
                            status=status.HTTP_409_CONFLICT)
        services.cancel_order(order, request.user, serializer.validated_data["reason"])
        return Response(OrderDetailSerializer(order_detail_queryset().get(pk=order.pk)).data)


# --------------------------------------------------------------------------
# Vendor fulfilment
# --------------------------------------------------------------------------
class VendorOrderItemSerializer(OrderItemSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_created_at = serializers.DateTimeField(source="order.created_at", read_only=True)
    payment_status = serializers.CharField(source="order.payment_status", read_only=True)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    vendor_earnings = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    allowed_next_statuses = serializers.SerializerMethodField()

    class Meta(OrderItemSerializer.Meta):
        fields = ["id", "order_number", "order_created_at", "payment_status", "product", "product_slug",
                  "product_name", "variant_label", "quantity", "price", "subtotal", "commission_rate",
                  "vendor_earnings", "status", "status_display", "tracking_number", "allowed_next_statuses",
                  "updated_at"]

    def get_allowed_next_statuses(self, obj) -> list[str]:
        return sorted(obj.allowed_next_statuses())


class VendorOrderSerializer(serializers.ModelSerializer):
    """An order as one vendor sees it: their own lines plus delivery details."""

    shipping_address = ShippingAddressSerializer(source="*", read_only=True)
    items = serializers.SerializerMethodField()
    timeline = TimelineSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["order_number", "status", "payment_status", "payment_method", "created_at", "customer_note",
                  "shipping_address", "items", "timeline"]

    def get_items(self, obj) -> list[dict]:
        items = obj.items.filter(vendor=self.context["vendor"]).select_related("product", "order")
        return VendorOrderItemSerializer(items, many=True).data


class VendorOrderItemListView(VendorScopedMixin, generics.ListAPIView):
    """Order lines for the vendor's products. Filter with ``status`` and ``q`` (order number/product)."""

    serializer_class = VendorOrderItemSerializer

    @extend_schema(parameters=[OpenApiParameter("status", str, enum=OrderItem.Status.values),
                               OpenApiParameter("q", str)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            OrderItem.objects.filter(vendor=self.vendor)
            .select_related("order", "product")
            .order_by("-order__created_at", "id")
        )
        status_filter = self.request.query_params.get("status")
        if status_filter in OrderItem.Status.values:
            queryset = queryset.filter(status=status_filter)
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(Q(order__order_number__icontains=query) | Q(product_name__icontains=query))
        return queryset


class VendorOrderDetailView(VendorScopedMixin, generics.RetrieveAPIView):
    serializer_class = VendorOrderSerializer
    lookup_field = "order_number"

    def get_queryset(self):
        return Order.objects.filter(items__vendor=self.vendor).prefetch_related("timeline").distinct()

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "vendor": self.vendor}


class VendorOrderItemStatusView(VendorScopedMixin, APIView):
    """Advance one of the vendor's order lines. ``tracking_number`` is required when shipping."""

    @extend_schema(request=ItemStatusSerializer, responses=VendorOrderItemSerializer)
    def post(self, request, pk):
        item = get_object_or_404(OrderItem, pk=pk, vendor=self.vendor)
        serializer = ItemStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_item_status(item, serializer.validated_data["status"], request.user,
                                 serializer.validated_data["tracking_number"])
        item = OrderItem.objects.select_related("order", "product").get(pk=item.pk)
        return Response(VendorOrderItemSerializer(item).data)
