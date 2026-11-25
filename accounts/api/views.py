from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from cart.services import add_to_cart
from core.api.permissions import IsCustomer, IsVendor
from products.api.serializers import ProductListSerializer
from products.models import Product

from ..models import Wishlist
from .cookies import clear_refresh_cookie, move_refresh_to_cookie, refresh_from_request, wants_cookie
from .serializers import (
    CustomerRegistrationSerializer,
    OptionalRefreshSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TokenWithUserSerializer,
    UserSerializer,
    VendorRegistrationSerializer,
    VendorSummarySerializer,
)


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class _RegisterView(generics.CreateAPIView):
    """Send ``"use_cookie": true`` to receive the refresh token as an httpOnly cookie."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response = Response({"user": serializer.data, **_tokens_for(user)}, status=status.HTTP_201_CREATED)
        return move_refresh_to_cookie(response) if wants_cookie(request) else response


class CustomerRegisterView(_RegisterView):
    """Create a customer account and return JWT tokens."""

    serializer_class = CustomerRegistrationSerializer


class VendorRegisterView(_RegisterView):
    """Apply as a vendor. The store starts in ``pending`` status until an administrator approves it."""

    serializer_class = VendorRegistrationSerializer


class LoginView(TokenObtainPairView):
    """
    Obtain an access/refresh JWT pair. ``username`` accepts a username or an email address.
    Browser apps should send ``"use_cookie": true``: the refresh token is then set as an
    httpOnly cookie and omitted from the body.
    """

    serializer_class = TokenWithUserSerializer
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200 and wants_cookie(request):
            move_refresh_to_cookie(response)
        return response


class RefreshView(TokenRefreshView):
    """
    Exchange a refresh token for a new access token (refresh tokens rotate).
    Send ``refresh`` in the body, or rely on the httpOnly cookie plus the header
    ``X-Requested-With: XMLHttpRequest``.
    """

    throttle_scope = "auth"

    @extend_schema(request=OptionalRefreshSerializer, responses=TokenRefreshSerializer)
    def post(self, request, *args, **kwargs):
        token, from_cookie = refresh_from_request(request)
        serializer = self.get_serializer(data={"refresh": token or ""})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc
        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        return move_refresh_to_cookie(response) if from_cookie else response


class LogoutView(APIView):
    """Blacklist the refresh token (body or cookie) and clear the refresh cookie."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(request=OptionalRefreshSerializer, responses={205: None})
    def post(self, request):
        token, _ = refresh_from_request(request)
        if not token:
            raise ValidationError({"refresh": ["This field is required."]})
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            response = Response({"detail": "Token is invalid or expired.", "code": "token_not_valid"},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            response = Response(status=status.HTTP_205_RESET_CONTENT)
        clear_refresh_cookie(response)
        return response


class MeView(generics.RetrieveUpdateAPIView):
    """The signed-in user's account. Customers can also update ``customer_profile`` (default address)."""

    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    """
    Change the password. Every token issued before the change stops working (on all devices),
    so a fresh ``access``/``refresh`` pair is returned. If the caller uses the refresh cookie,
    the new refresh token is set in that cookie instead of the body.
    """

    @extend_schema(request=PasswordChangeSerializer, responses={200: TokenRefreshSerializer})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        had_cookie = settings.JWT_REFRESH_COOKIE_NAME in request.COOKIES
        user = serializer.save()
        if request.session.session_key:
            update_session_auth_hash(request, user)
        refresh = RefreshToken.for_user(user)
        response = Response({"access": str(refresh.access_token), "refresh": str(refresh)})
        return move_refresh_to_cookie(response) if had_cookie else response


class PasswordResetRequestView(APIView):
    """Always returns 202 so the endpoint cannot be used to discover registered emails."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=PasswordResetRequestSerializer, responses={202: None})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=PasswordResetConfirmSerializer, responses={204: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorApplicationView(generics.RetrieveAPIView):
    """Approval status of the signed-in vendor's application (works while pending)."""

    serializer_class = VendorSummarySerializer
    permission_classes = [IsVendor]

    def get_object(self):
        return self.request.user.vendor_profile


# --------------------------------------------------------------------------
# Wishlist
# --------------------------------------------------------------------------
class WishlistView(APIView):
    permission_classes = [IsCustomer]

    def _wishlist(self, request):
        return Wishlist.objects.get_or_create(user=request.user)[0]

    @extend_schema(responses=ProductListSerializer(many=True))
    def get(self, request):
        products = self._wishlist(request).products.for_listing().prefetch_related("variants")
        return Response(ProductListSerializer(products, many=True, context={"request": request}).data)

    @extend_schema(request={"application/json": {"type": "object", "properties": {"product": {"type": "integer"}},
                                                 "required": ["product"]}},
                   responses={201: None})
    def post(self, request):
        product = get_object_or_404(Product.objects.visible(), pk=request.data.get("product"))
        self._wishlist(request).products.add(product)
        return Response(status=status.HTTP_201_CREATED)


class WishlistItemView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(responses={204: None})
    def delete(self, request, product_id):
        wishlist = Wishlist.objects.get_or_create(user=request.user)[0]
        product = get_object_or_404(wishlist.products.all(), pk=product_id)
        wishlist.products.remove(product)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WishlistMoveToCartView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(request=None, responses={204: None})
    def post(self, request, product_id):
        wishlist = Wishlist.objects.get_or_create(user=request.user)[0]
        product = get_object_or_404(wishlist.products.all(), pk=product_id)
        add_to_cart(request.user, product, 1)  # raises CartError -> 400 (e.g. variant required)
        wishlist.products.remove(product)
        return Response(status=status.HTTP_204_NO_CONTENT)
