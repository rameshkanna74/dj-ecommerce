import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from accounts.permissions import CustomerRequiredMixin, VendorRequiredMixin, customer_required, vendor_required
from core.mixins import SafePaginationMixin

from . import services
from .forms import CancelOrderForm, CheckoutForm, CouponApplyForm, OrderItemStatusForm
from .models import Order, OrderItem
from .payments import payment_instructions

SESSION_COUPON = "checkout_coupon"
SESSION_TOKEN = "checkout_token"


def _checkout_token(request, rotate=False):
    if rotate or not request.session.get(SESSION_TOKEN):
        request.session[SESSION_TOKEN] = secrets.token_urlsafe(32)
    return request.session[SESSION_TOKEN]


def _initial_shipping(user):
    profile = getattr(user, "customer_profile", None)
    initial = {"full_name": user.get_full_name(), "phone": user.phone}
    if profile is not None:
        initial.update(
            address=profile.address,
            city=profile.city,
            state=profile.state,
            postal_code=profile.zip_code,
            country=profile.country,
        )
    return initial


def _save_default_address(user, data):
    profile = getattr(user, "customer_profile", None)
    if profile is None:
        return
    profile.address = data["address"]
    profile.city = data["city"]
    profile.state = data["state"]
    profile.zip_code = data["postal_code"]
    profile.country = data["country"]
    profile.save(update_fields=["address", "city", "state", "zip_code", "country", "updated_at"])


@customer_required
def checkout(request):
    if request.method == "POST":
        # A repeated submission (double click, refresh, back button) returns the order already placed.
        token = request.POST.get("checkout_token", "")
        existing = Order.objects.filter(checkout_token=token, user=request.user).first() if token else None
        if existing:
            messages.info(request, f"Order {existing.order_number} has already been placed.")
            return redirect(existing.get_absolute_url())

    coupon_code = request.session.get(SESSION_COUPON, "")
    summary = services.build_checkout_summary(request.user, coupon_code)
    if summary.is_empty:
        messages.warning(request, "Your cart is empty.")
        return redirect("cart:view")
    if summary.coupon_error and coupon_code:
        request.session.pop(SESSION_COUPON, None)
        messages.warning(request, f"Coupon {coupon_code} was removed: {summary.coupon_error}")
        coupon_code = ""

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            token = form.cleaned_data["checkout_token"]
            if token != request.session.get(SESSION_TOKEN):
                messages.warning(request, "Your checkout session expired. Please review your order and try again.")
                return redirect("orders:checkout")
            try:
                order, _ = services.place_order(
                    request.user,
                    shipping=form.shipping_data(),
                    payment_method=form.cleaned_data["payment_method"],
                    coupon_code=coupon_code,
                    checkout_token=token,
                    customer_note=form.cleaned_data["customer_note"],
                )
            except services.CheckoutError as exc:
                messages.error(request, str(exc))
                return redirect("cart:view")
            if form.cleaned_data.get("save_address"):
                _save_default_address(request.user, form.cleaned_data)
            request.session.pop(SESSION_COUPON, None)
            request.session.pop(SESSION_TOKEN, None)
            messages.success(request, f"Thank you! Order {order.order_number} has been placed.")
            return redirect(order.get_absolute_url())
    else:
        form = CheckoutForm(initial={**_initial_shipping(request.user), "checkout_token": _checkout_token(request)})

    return render(
        request,
        "orders/checkout.html",
        {"form": form, "summary": summary, "coupon_form": CouponApplyForm(), "coupon_code": coupon_code},
    )


@require_POST
@customer_required
def apply_coupon(request):
    form = CouponApplyForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please enter a coupon code.")
        return redirect("orders:checkout")
    code = form.cleaned_data["code"]
    summary = services.build_checkout_summary(request.user, code)
    if summary.coupon_error:
        request.session.pop(SESSION_COUPON, None)
        messages.error(request, summary.coupon_error)
    else:
        request.session[SESSION_COUPON] = summary.coupon.code
        messages.success(request, f"Coupon {summary.coupon.code} applied.")
    return redirect("orders:checkout")


@require_POST
@customer_required
def remove_coupon(request):
    request.session.pop(SESSION_COUPON, None)
    messages.info(request, "Coupon removed.")
    return redirect("orders:checkout")


# --------------------------------------------------------------------------
# Customer orders
# --------------------------------------------------------------------------
class OrderListView(CustomerRequiredMixin, SafePaginationMixin, ListView):
    template_name = "orders/list.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        queryset = Order.objects.filter(user=self.request.user).annotate(item_count=Count("items"))
        status = self.request.GET.get("status")
        if status in Order.Status.values:
            queryset = queryset.filter(status=status)
        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        context["status_choices"] = Order.Status.choices
        return context


def _customer_order(request, order_number):
    return get_object_or_404(
        Order.objects.select_related("coupon").prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("product", "vendor")),
            "timeline",
        ),
        order_number=order_number,
        user=request.user,
    )


@customer_required
def order_detail(request, order_number):
    order = _customer_order(request, order_number)
    return render(
        request,
        "orders/detail.html",
        {
            "order": order,
            "can_cancel": order.can_customer_cancel(),
            "cancel_form": CancelOrderForm(),
            "payment_instructions": payment_instructions(order),
        },
    )


@require_POST
@customer_required
def cancel_order(request, order_number):
    order = _customer_order(request, order_number)
    form = CancelOrderForm(request.POST)
    if not order.can_customer_cancel() or not form.is_valid():
        messages.error(request, "This order can no longer be cancelled. Please contact support.")
        return redirect(order.get_absolute_url())
    try:
        services.cancel_order(order, request.user, form.cleaned_data["reason"])
    except services.OrderWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Order {order.order_number} has been cancelled.")
    return redirect(order.get_absolute_url())


@login_required
def invoice_view(request, order_number):
    """Printable invoice for the order's customer or a platform administrator."""
    queryset = Order.objects.select_related("user").prefetch_related("items")
    if request.user.is_platform_admin:
        order = get_object_or_404(queryset, order_number=order_number)
    else:
        order = get_object_or_404(queryset, order_number=order_number, user=request.user)
    return render(request, "orders/invoice.html", {"order": order})


# --------------------------------------------------------------------------
# Vendor fulfilment
# --------------------------------------------------------------------------
class VendorOrderListView(VendorRequiredMixin, SafePaginationMixin, ListView):
    template_name = "orders/vendor/order_list.html"
    context_object_name = "order_items"
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            OrderItem.objects.filter(vendor=self.vendor)
            .select_related("order", "order__user", "product")
            .order_by("-order__created_at", "id")
        )
        status = self.request.GET.get("status")
        if status in OrderItem.Status.values:
            queryset = queryset.filter(status=status)
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(Q(order__order_number__icontains=query) | Q(product_name__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = dict(
            OrderItem.objects.filter(vendor=self.vendor).values_list("status").annotate(n=Count("id")).order_by()
        )
        context.update(
            {
                "status_filter": self.request.GET.get("status", ""),
                "query": self.request.GET.get("q", ""),
                "status_counts": [(value, label, counts.get(value, 0)) for value, label in OrderItem.Status.choices],
            }
        )
        return context


@vendor_required
def vendor_order_detail(request, order_number):
    vendor = request.user.vendor_profile
    order = get_object_or_404(
        Order.objects.select_related("user").filter(items__vendor=vendor).distinct(), order_number=order_number
    )
    items = list(order.items.filter(vendor=vendor).select_related("product", "variant"))
    forms = [(item, OrderItemStatusForm(item=item, prefix=f"item-{item.pk}")) for item in items]
    return render(
        request,
        "orders/vendor/order_detail.html",
        {
            "order": order,
            "item_forms": forms,
            "vendor_subtotal": sum((i.subtotal for i in items if i.status != OrderItem.Status.CANCELLED), 0),
            "timeline": order.timeline.all(),
        },
    )


@require_POST
@vendor_required
def vendor_update_item(request, pk):
    item = get_object_or_404(
        OrderItem.objects.select_related("order"), pk=pk, vendor=request.user.vendor_profile
    )
    form = OrderItemStatusForm(request.POST, item=item, prefix=f"item-{item.pk}")
    if not form.is_valid():
        messages.error(request, "Please choose a valid next status.")
    else:
        try:
            services.set_item_status(
                item, form.cleaned_data["status"], request.user, form.cleaned_data["tracking_number"]
            )
            messages.success(request, f'"{item.display_name}" updated.')
        except services.OrderWorkflowError as exc:
            messages.error(request, str(exc))
    return redirect("orders:vendor_order_detail", order_number=item.order.order_number)
