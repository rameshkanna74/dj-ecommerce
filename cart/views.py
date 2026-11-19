from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import customer_required
from core.utils import safe_redirect_target
from products.models import Product, ProductVariant

from . import services
from .models import CartItem


def _parse_quantity(raw, default=1):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default if raw in (None, "") else 0


@customer_required
def cart_view(request):
    return render(request, "cart/cart.html", {"cart": services.get_cart_summary(request.user)})


@require_POST
@customer_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product.objects.visible().prefetch_related("variants"), pk=product_id)
    variant = None
    variant_id = request.POST.get("variant")
    if variant_id:
        variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
    quantity = _parse_quantity(request.POST.get("quantity"))
    try:
        services.add_to_cart(request.user, product, quantity, variant)
    except services.CartError as exc:
        messages.error(request, str(exc))
        return redirect(product.get_absolute_url())
    messages.success(request, f'"{product.name}" added to your cart.')
    return redirect(safe_redirect_target(request, request.POST.get("next"), "cart:view"))


@require_POST
@customer_required
def update_cart_quantity(request, item_id):
    item = get_object_or_404(CartItem.objects.select_related("product", "variant"), pk=item_id, user=request.user)
    quantity = _parse_quantity(request.POST.get("quantity"), default=item.quantity)
    try:
        services.update_quantity(item, quantity)
        messages.success(request, f'Updated quantity for "{item.product.name}".')
    except services.CartError as exc:
        messages.error(request, f'{item.product.name}: {exc}')
    return redirect("cart:view")


@require_POST
@customer_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem.objects.select_related("product"), pk=item_id, user=request.user)
    name = item.product.name
    item.delete()
    messages.success(request, f'"{name}" removed from your cart.')
    return redirect("cart:view")


@require_POST
@customer_required
def toggle_save_for_later(request, item_id):
    item = get_object_or_404(
        CartItem.objects.select_related("product__category", "product__vendor__user", "variant"),
        pk=item_id,
        user=request.user,
    )
    try:
        services.set_saved_for_later(item, not item.is_saved_for_later)
    except services.CartError as exc:
        messages.error(request, f'{item.product.name}: {exc}')
        return redirect("cart:view")
    status = "saved for later" if item.is_saved_for_later else "moved back to your cart"
    messages.success(request, f'"{item.product.name}" {status}.')
    return redirect("cart:view")
