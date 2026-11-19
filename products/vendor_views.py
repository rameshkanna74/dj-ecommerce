"""Vendor-facing catalogue management. Every queryset is scoped to the signed-in vendor."""

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DeleteView, ListView

from accounts.permissions import VendorRequiredMixin, vendor_required
from core.mixins import SafePaginationMixin

from .forms import AnswerForm, ProductForm, ProductImageFormSet, ProductVariantFormSet, StockUpdateForm
from .models import Product, ProductQuestion, ProductVariant, Review


class VendorProductListView(VendorRequiredMixin, SafePaginationMixin, ListView):
    template_name = "products/vendor/product_list.html"
    context_object_name = "products"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            Product.objects.by_vendor(self.vendor)
            .select_related("category")
            .prefetch_related("variants")
            .with_units_sold()
            .order_by("-created_at")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(slug__icontains=query))
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["status_filter"] = self.request.GET.get("status", "")
        return context


def _product_form_view(request, product=None):
    vendor = request.user.vendor_profile
    instance = product or Product(vendor=vendor)
    data = request.POST if request.method == "POST" else None
    files = request.FILES if request.method == "POST" else None
    form = ProductForm(data, files, instance=instance)
    variant_formset = ProductVariantFormSet(data, instance=instance, prefix="variants")
    image_formset = ProductImageFormSet(data, files, instance=instance, prefix="images")

    if request.method == "POST" and form.is_valid() and variant_formset.is_valid() and image_formset.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            saved.vendor = vendor  # ownership is always server-assigned
            saved.save()
            variant_formset.instance = saved
            variant_formset.save()
            image_formset.instance = saved
            image_formset.save()
        messages.success(request, f'"{saved.name}" has been {"updated" if product else "created"}.')
        return redirect("products:vendor_list")

    return render(
        request,
        "products/vendor/product_form.html",
        {
            "form": form,
            "variant_formset": variant_formset,
            "image_formset": image_formset,
            "product": product,
        },
    )


@vendor_required
def product_create(request):
    return _product_form_view(request)


@vendor_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk, vendor=request.user.vendor_profile)
    return _product_form_view(request, product)


class ProductDeleteView(VendorRequiredMixin, DeleteView):
    template_name = "products/vendor/product_confirm_delete.html"
    success_url = reverse_lazy("products:vendor_list")
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.by_vendor(self.vendor)

    def form_valid(self, form):
        product = self.get_object()
        try:
            product.delete()
        except ProtectedError:
            # Products with order history must stay for invoices; hide them instead.
            Product.objects.filter(pk=product.pk).update(is_active=False)
            messages.warning(
                self.request,
                f'"{product.name}" has existing orders, so it was hidden from the marketplace instead of deleted.',
            )
        else:
            messages.success(self.request, f'"{product.name}" was deleted.')
        return redirect(self.success_url)


@vendor_required
def inventory(request):
    vendor = request.user.vendor_profile
    products = (
        Product.objects.by_vendor(vendor)
        .select_related("category")
        .prefetch_related("variants")
        .order_by("stock", "name")
    )
    low_stock_only = request.GET.get("low") == "1"
    if low_stock_only:
        products = products.filter(stock__lte=5)
    totals = Product.objects.by_vendor(vendor).aggregate(units=Sum("stock"))
    return render(
        request,
        "products/vendor/inventory.html",
        {"products": products, "low_stock_only": low_stock_only, "total_units": totals["units"] or 0},
    )


@vendor_required
def update_stock(request, pk):
    if request.method != "POST":
        return redirect("products:inventory")
    vendor = request.user.vendor_profile
    variant_id = request.POST.get("variant")
    form = StockUpdateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Stock must be a whole number of 0 or more.")
        return redirect("products:inventory")
    if variant_id:
        target = get_object_or_404(ProductVariant, pk=variant_id, product__pk=pk, product__vendor=vendor)
        name = str(target)
    else:
        target = get_object_or_404(Product, pk=pk, vendor=vendor)
        name = target.name
    target.stock = form.cleaned_data["stock"]
    target.save(update_fields=["stock"])
    messages.success(request, f"Stock for {name} set to {target.stock}.")
    return redirect("products:inventory")


@vendor_required
def vendor_reviews(request):
    reviews = (
        Review.objects.filter(product__vendor=request.user.vendor_profile)
        .select_related("product", "user")
        .order_by("-created_at")
    )
    rating = request.GET.get("rating")
    if rating in {"1", "2", "3", "4", "5"}:
        reviews = reviews.filter(rating=int(rating))
    return render(request, "products/vendor/reviews.html", {"reviews": reviews[:100], "rating_filter": rating})


@vendor_required
def vendor_questions(request):
    questions = (
        ProductQuestion.objects.filter(product__vendor=request.user.vendor_profile)
        .select_related("product", "user")
        .order_by("is_answered", "-created_at")
    )
    return render(request, "products/vendor/questions.html", {"questions": questions[:100], "form": AnswerForm()})


@vendor_required
def answer_question(request, pk):
    question = get_object_or_404(ProductQuestion, pk=pk, product__vendor=request.user.vendor_profile)
    if request.method != "POST":
        return redirect("products:vendor_questions")
    form = AnswerForm(request.POST, instance=question)
    if form.is_valid():
        answered = form.save(commit=False)
        answered.is_answered = True
        answered.answered_by = request.user
        answered.answered_at = timezone.now()
        answered.save()
        messages.success(request, "Your answer has been published.")
    else:
        messages.error(request, "Please write an answer.")
    return redirect("products:vendor_questions")
