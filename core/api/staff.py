"""Administrator endpoints (`/api/v1/staff/...`). Business actions go through the service layer."""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import VendorProfile
from core.emails import send_templated_email
from orders import payments, services
from orders.api import ItemStatusSerializer, OrderDetailSerializer, OrderItemSerializer, OrderSummarySerializer
from orders.api import order_detail_queryset
from orders.models import Coupon, Order, OrderItem
from products.api.serializers import CategorySerializer, VendorReviewSerializer
from products.models import Category, Product, Review

from .permissions import IsPlatformAdmin

User = get_user_model()


class StaffMixin:
    permission_classes = [IsPlatformAdmin]


# ---- serializers ------------------------------------------------------------
class StaffVendorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    is_user_active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model = VendorProfile
        fields = ["id", "username", "email", "is_user_active", "business_name", "store_slug", "business_email",
                  "business_phone", "business_address", "business_city", "business_state", "business_zip_code",
                  "business_country", "tax_id", "business_registration_number", "approval_status",
                  "rejection_reason", "approved_at", "commission_rate", "created_at"]
        read_only_fields = [f for f in fields if f != "commission_rate"]


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class PaymentSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ["id", "code", "description", "discount_type", "value", "min_order_amount", "active", "valid_from",
                  "valid_to", "usage_limit", "used_count"]
        read_only_fields = ["id", "used_count"]

    def validate(self, attrs):
        get = lambda k: attrs.get(k, getattr(self.instance, k, None))  # noqa: E731
        if get("valid_from") and get("valid_to") and get("valid_to") <= get("valid_from"):
            raise serializers.ValidationError({"valid_to": "Must be after valid_from."})
        if get("discount_type") == Coupon.DiscountType.PERCENTAGE and get("value") and get("value") > 100:
            raise serializers.ValidationError({"value": "A percentage discount cannot exceed 100."})
        if get("value") is not None and get("value") <= 0:
            raise serializers.ValidationError({"value": "Must be greater than zero."})
        if self.instance and get("usage_limit") is not None and get("usage_limit") < self.instance.used_count:
            raise serializers.ValidationError({"usage_limit": "Cannot be lower than the number of times already used."})
        return attrs


class StaffCategorySerializer(CategorySerializer):
    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ["is_active"]
        read_only_fields = ["slug"]


class StaffUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "is_active", "is_staff", "date_joined",
                  "last_login"]
        read_only_fields = [f for f in fields if f != "is_active"]


class StaffProductSerializer(serializers.ModelSerializer):
    vendor = serializers.CharField(source="vendor.business_name", read_only=True, default=None)
    category = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "vendor", "category", "price", "stock", "is_active", "is_featured",
                  "average_rating", "review_count", "created_at"]
        read_only_fields = [f for f in fields if f not in ("is_active", "is_featured")]


class StaffReviewSerializer(VendorReviewSerializer):
    class Meta(VendorReviewSerializer.Meta):
        read_only_fields = [f for f in VendorReviewSerializer.Meta.fields if f != "is_visible"]


# ---- viewsets ---------------------------------------------------------------
class StaffVendorViewSet(StaffMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                         viewsets.GenericViewSet):
    """Vendor applications and stores. PATCH may change ``commission_rate`` only."""

    serializer_class = StaffVendorSerializer
    http_method_names = ["get", "patch", "post", "head", "options"]

    @extend_schema(parameters=[OpenApiParameter("status", str, enum=VendorProfile.Approval.values)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = VendorProfile.objects.select_related("user").order_by("-created_at")
        status_filter = self.request.query_params.get("status")
        if status_filter in VendorProfile.Approval.values:
            queryset = queryset.filter(approval_status=status_filter)
        return queryset

    def _transition(self, request, method):
        vendor = self.get_object()
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if method == "approve":
            vendor.approve(by=request.user)
        else:
            getattr(vendor, method)(by=request.user, reason=serializer.validated_data["reason"])
        send_templated_email("vendor_status", {"vendor": vendor}, [vendor.business_email or vendor.user.email])
        return Response(StaffVendorSerializer(vendor).data)

    @extend_schema(request=None, responses=StaffVendorSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._transition(request, "approve")

    @extend_schema(request=ReasonSerializer, responses=StaffVendorSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if self.get_object().is_approved:
            return Response({"detail": "Approved vendors must be suspended, not rejected.",
                             "code": "invalid_transition"}, status=status.HTTP_409_CONFLICT)
        return self._transition(request, "reject")

    @extend_schema(request=ReasonSerializer, responses=StaffVendorSerializer)
    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        return self._transition(request, "suspend")


class StaffOrderViewSet(StaffMixin, viewsets.ReadOnlyModelViewSet):
    """All orders. Filter with ``status``, ``payment_status`` and ``q``."""

    lookup_field = "order_number"

    def get_serializer_class(self):
        return OrderDetailSerializer if self.action != "list" else OrderSummarySerializer

    @extend_schema(parameters=[OpenApiParameter("status", str, enum=Order.Status.values),
                               OpenApiParameter("payment_status", str, enum=Order.PaymentStatus.values),
                               OpenApiParameter("q", str)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if self.action != "list":
            return order_detail_queryset()
        queryset = Order.objects.select_related("user").order_by("-created_at")
        params = self.request.query_params
        if params.get("status") in Order.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("payment_status") in Order.PaymentStatus.values:
            queryset = queryset.filter(payment_status=params["payment_status"])
        query = params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(order_number__icontains=query) | Q(user__email__icontains=query)
                | Q(shipping_full_name__icontains=query)
            )
        return queryset

    def _detail(self, order):
        return Response(OrderDetailSerializer(order_detail_queryset().get(pk=order.pk)).data)

    @extend_schema(request=PaymentSerializer, responses=OrderDetailSerializer)
    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, order_number=None):
        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = payments.mark_order_paid(self.get_object(), request.user, serializer.validated_data["reference"])
        return self._detail(order)

    @extend_schema(request=ReasonSerializer, responses=OrderDetailSerializer)
    @action(detail=True, methods=["post"])
    def refund(self, request, order_number=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = payments.mark_order_refunded(self.get_object(), request.user, serializer.validated_data["reason"])
        return self._detail(order)

    @extend_schema(request=ReasonSerializer, responses=OrderDetailSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, order_number=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.cancel_order(self.get_object(), request.user,
                                      serializer.validated_data["reason"] or "Cancelled by administrator.")
        return self._detail(order)


class StaffOrderItemStatusView(StaffMixin, APIView):
    @extend_schema(request=ItemStatusSerializer, responses=OrderItemSerializer)
    def post(self, request, pk):
        item = get_object_or_404(OrderItem, pk=pk)
        serializer = ItemStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_item_status(item, serializer.validated_data["status"], request.user,
                                 serializer.validated_data["tracking_number"])
        return Response(OrderItemSerializer(OrderItem.objects.select_related("vendor", "product").get(pk=pk)).data)


class StaffCouponViewSet(StaffMixin, viewsets.ModelViewSet):
    serializer_class = CouponSerializer
    queryset = Coupon.objects.all()


class StaffCategoryViewSet(StaffMixin, viewsets.ModelViewSet):
    """Deleting a category that still has products returns 409; deactivate it instead."""

    serializer_class = StaffCategorySerializer
    queryset = Category.objects.annotate(product_count=Count("products"))


class StaffUserViewSet(StaffMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                       viewsets.GenericViewSet):
    """Users. PATCH may change ``is_active`` only (not on your own account)."""

    serializer_class = StaffUserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(parameters=[OpenApiParameter("role", str, enum=User.Role.values), OpenApiParameter("q", str)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = User.objects.order_by("-date_joined")
        if self.request.query_params.get("role") in User.Role.values:
            queryset = queryset.filter(role=self.request.query_params["role"])
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(Q(username__icontains=query) | Q(email__icontains=query))
        return queryset

    def perform_update(self, serializer):
        if serializer.instance.pk == self.request.user.pk:
            raise serializers.ValidationError({"is_active": "You cannot change your own account status."})
        serializer.save()


class StaffProductViewSet(StaffMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                          viewsets.GenericViewSet):
    """All products (stock monitoring, featuring, take-down). PATCH ``is_active`` / ``is_featured``."""

    serializer_class = StaffProductSerializer
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(parameters=[OpenApiParameter("low_stock", bool), OpenApiParameter("q", str)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Product.objects.select_related("vendor", "category").order_by("-created_at")
        if self.request.query_params.get("low_stock") in {"1", "true"}:
            queryset = queryset.filter(is_active=True, stock__lte=5).order_by("stock")
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset


class StaffReviewViewSet(StaffMixin, mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Review moderation. PATCH ``is_visible``; ratings are recalculated automatically."""

    serializer_class = StaffReviewSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Review.objects.select_related("product", "user").order_by("-created_at")
        visible = self.request.query_params.get("visible")
        if visible in {"true", "false"}:
            queryset = queryset.filter(is_visible=visible == "true")
        return queryset
