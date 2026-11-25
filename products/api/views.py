from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.models import VendorProfile
from core.api.caching import PublicCacheMixin
from core.api.permissions import IsCustomer, VendorScopedMixin, is_schema_generation
from products.forms import ProductFilterForm
from products.models import Category, Product, ProductImage, ProductQuestion, ProductVariant, Review
from products.services import filter_catalogue, subscribe_stock_alert, user_has_purchased

from .serializers import (
    AnswerSerializer,
    CategorySerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    QuestionSerializer,
    ReviewSerializer,
    StoreSerializer,
    VariantSerializer,
    VendorProductSerializer,
    VendorReviewSerializer,
)

CATALOGUE_PARAMS = [
    OpenApiParameter("q", str, description="Search name, description and category"),
    OpenApiParameter("category", str, description="Category slug"),
    OpenApiParameter("min_price", OpenApiTypes.DECIMAL),
    OpenApiParameter("max_price", OpenApiTypes.DECIMAL),
    OpenApiParameter("in_stock", bool),
    OpenApiParameter("sort", str, enum=[c[0] for c in ProductFilterForm.SORT_CHOICES]),
]


def catalogue_queryset():
    return Product.objects.visible().for_listing().prefetch_related("variants")


def filtered_catalogue(request, queryset):
    form = ProductFilterForm(request.query_params)
    if not form.is_valid():
        raise ValidationError(form.errors.get_json_data())
    return filter_catalogue(queryset, form.cleaned_data)


class CategoryViewSet(PublicCacheMixin, viewsets.ReadOnlyModelViewSet):
    """Active categories."""

    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    queryset = Category.objects.active().annotate(
        product_count=Count(
            "products",
            filter=Q(products__is_active=True)
            & (Q(products__vendor__isnull=True)
               | Q(products__vendor__approval_status="approved", products__vendor__user__is_active=True)),
        )
    )
    lookup_field = "slug"
    pagination_class = None


class ProductViewSet(PublicCacheMixin, viewsets.ReadOnlyModelViewSet):
    """Public catalogue: only active products from approved vendors in active categories."""

    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        if self.action == "retrieve":
            return Product.objects.visible().select_related("category", "vendor").prefetch_related("images", "variants")
        return catalogue_queryset()

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer

    def filter_queryset(self, queryset):
        if self.action == "list":
            return filtered_catalogue(self.request, queryset)
        return queryset

    @extend_schema(parameters=CATALOGUE_PARAMS)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # ---- reviews -------------------------------------------------------
    @extend_schema(methods=["GET"], responses=ReviewSerializer(many=True))
    @extend_schema(methods=["POST"], request=ReviewSerializer, responses={201: ReviewSerializer})
    @action(detail=True, methods=["get", "post"], serializer_class=ReviewSerializer)
    def reviews(self, request, slug=None):
        product = self.get_object()
        if request.method == "GET":
            page = self.paginate_queryset(product.reviews.filter(is_visible=True).select_related("user"))
            return self.get_paginated_response(ReviewSerializer(page, many=True).data)
        self._require_customer(request)
        duplicate = Response({"detail": "You have already reviewed this product.", "code": "duplicate_review"},
                             status=status.HTTP_409_CONFLICT)
        if Review.objects.filter(product=product, user=request.user).exists():
            return duplicate
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save(product=product, user=request.user,
                                is_verified_purchase=user_has_purchased(request.user, product))
        except IntegrityError:  # a concurrent identical POST won the unique (product, user) race
            return duplicate
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ---- questions -----------------------------------------------------
    @extend_schema(methods=["GET"], responses=QuestionSerializer(many=True))
    @extend_schema(methods=["POST"], request=QuestionSerializer, responses={201: QuestionSerializer})
    @action(detail=True, methods=["get", "post"], serializer_class=QuestionSerializer)
    def questions(self, request, slug=None):
        product = self.get_object()
        if request.method == "GET":
            queryset = product.questions.filter(is_public=True).select_related("user")
            page = self.paginate_queryset(queryset)
            return self.get_paginated_response(QuestionSerializer(page, many=True).data)
        self._require_customer(request)
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product, user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ---- stock alerts ---------------------------------------------------
    @extend_schema(request=None, responses={201: None, 200: None})
    @action(detail=True, methods=["post"], url_path="stock-alert")
    def stock_alert(self, request, slug=None):
        product = self.get_object()
        self._require_customer(request)
        if product.is_in_stock:
            return Response({"detail": "This product is in stock.", "code": "in_stock"},
                            status=status.HTTP_400_BAD_REQUEST)
        _, created = subscribe_stock_alert(request.user, product)
        return Response({"subscribed": True}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def _require_customer(self, request):
        if not IsCustomer().has_permission(request, self):
            self.permission_denied(request, message=IsCustomer.message)


class ReviewViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                    viewsets.GenericViewSet):
    """A customer's own review: read, edit or delete."""

    serializer_class = ReviewSerializer
    permission_classes = [IsCustomer]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if is_schema_generation(self):
            return Review.objects.none()
        return Review.objects.filter(user=self.request.user).select_related("product", "user")


class StoreViewSet(PublicCacheMixin, viewsets.ReadOnlyModelViewSet):
    """Public vendor storefronts."""

    serializer_class = StoreSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "store_slug"
    lookup_url_kwarg = "slug"

    def get_queryset(self):
        return VendorProfile.objects.filter(approval_status="approved", user__is_active=True).order_by("business_name")

    @extend_schema(parameters=CATALOGUE_PARAMS, responses=ProductListSerializer(many=True))
    @action(detail=True, methods=["get"], serializer_class=ProductListSerializer)
    def products(self, request, slug=None):
        vendor = self.get_object()
        queryset = filtered_catalogue(request, catalogue_queryset().filter(vendor=vendor))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(ProductListSerializer(page, many=True, context={"request": request}).data)


# --------------------------------------------------------------------------
# Vendor catalogue management
# --------------------------------------------------------------------------
class VendorProductViewSet(VendorScopedMixin, viewsets.ModelViewSet):
    """The signed-in vendor's products (including hidden ones)."""

    serializer_class = VendorProductSerializer

    def get_queryset(self):
        if is_schema_generation(self):
            return Product.objects.none()
        queryset = (
            Product.objects.by_vendor(self.vendor)
            .select_related("category")
            .prefetch_related("variants", "images")
            .with_units_sold()
            .order_by("-created_at")
        )
        status_filter = self.request.query_params.get("status")
        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

    def perform_create(self, serializer):
        serializer.save(vendor=self.vendor)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        try:
            product.delete()
        except ProtectedError:
            Product.objects.filter(pk=product.pk).update(is_active=False)
            return Response(
                {"detail": "This product has existing orders, so it was hidden instead of deleted.",
                 "code": "hidden_instead"},
                status=status.HTTP_200_OK,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class _VendorProductChildViewSet(VendorScopedMixin, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    pagination_class = None

    def get_product(self):
        if not hasattr(self, "_product"):
            self._product = get_object_or_404(Product, pk=self.kwargs["product_pk"], vendor=self.vendor)
        return self._product

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "product_pk" in self.kwargs:
            context["product"] = self.get_product()
        return context

    def perform_create(self, serializer):
        serializer.save(product=self.get_product())


class VendorVariantViewSet(_VendorProductChildViewSet):
    """Options (size, colour, ...) for one of the vendor's products. Each has its own stock and price."""

    serializer_class = VariantSerializer

    def get_queryset(self):
        return ProductVariant.objects.filter(product=self.get_product()).select_related("product")

    def perform_destroy(self, instance):
        if instance.order_items.exists():
            raise ProtectedError("Variant has order lines.", {instance})  # -> 409; set is_active=false instead
        instance.delete()


class VendorProductImageViewSet(_VendorProductChildViewSet):
    """Gallery images (multipart upload; JPG/PNG/WebP/GIF up to the configured size)."""

    serializer_class = ProductImageSerializer

    def get_queryset(self):
        return ProductImage.objects.filter(product=self.get_product())


class VendorReviewViewSet(VendorScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = VendorReviewSerializer

    def get_queryset(self):
        if is_schema_generation(self):
            return Review.objects.none()
        queryset = Review.objects.filter(product__vendor=self.vendor).select_related("product", "user")
        rating = self.request.query_params.get("rating")
        if rating in {"1", "2", "3", "4", "5"}:
            queryset = queryset.filter(rating=int(rating))
        return queryset


class VendorQuestionViewSet(VendorScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = QuestionSerializer

    def get_queryset(self):
        if is_schema_generation(self):
            return ProductQuestion.objects.none()
        queryset = (
            ProductQuestion.objects.filter(product__vendor=self.vendor)
            .select_related("product", "user")
            .order_by("is_answered", "-created_at")
        )
        answered = self.request.query_params.get("answered")
        if answered in {"true", "false"}:
            queryset = queryset.filter(is_answered=answered == "true")
        return queryset

    @extend_schema(request=AnswerSerializer, responses=QuestionSerializer)
    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        question = self.get_object()
        serializer = AnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question.answer = serializer.validated_data["answer"]
        question.is_answered = True
        question.answered_by = request.user
        question.answered_at = timezone.now()
        question.save()
        return Response(QuestionSerializer(question).data)
