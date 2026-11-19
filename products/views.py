"""Public catalogue views and customer interactions (reviews, questions, alerts)."""

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from accounts.permissions import customer_required
from core.mixins import SafePaginationMixin

from .forms import ProductFilterForm, QuestionForm, ReviewForm
from .models import Category, Product, ProductQuestion, Review
from .services import filter_catalogue, subscribe_stock_alert, user_has_purchased

SESSION_RECENT_KEY = "recently_viewed"


def recently_viewed_products(request, exclude_id=None):
    ids = [pk for pk in request.session.get(SESSION_RECENT_KEY, []) if pk != exclude_id]
    if not ids:
        return []
    products = Product.objects.visible().for_listing().prefetch_related("variants").in_bulk(ids)
    return [products[pk] for pk in ids if pk in products]


def remember_product(request, product):
    limit = settings.CORECART_RECENTLY_VIEWED_LIMIT
    ids = [pk for pk in request.session.get(SESSION_RECENT_KEY, []) if pk != product.pk]
    request.session[SESSION_RECENT_KEY] = [product.pk, *ids][:limit]


class ProductListView(SafePaginationMixin, ListView):
    template_name = "products/list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_filter_form(self):
        if not hasattr(self, "_filter_form"):
            self._filter_form = ProductFilterForm(self.request.GET or None)
            self._filter_form.is_valid()
        return self._filter_form

    def get_queryset(self):
        form = self.get_filter_form()
        data = form.cleaned_data if form.is_bound else {}
        # Invalid fields are absent from cleaned_data, so they are simply ignored here.
        return filter_catalogue(Product.objects.visible().for_listing().prefetch_related("variants"), data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_filter_form()
        category_slug = form.cleaned_data.get("category") if form.is_bound else None
        filters = {"min_price": None, "max_price": None, "in_stock": False}
        if form.is_bound:
            filters.update({key: form.cleaned_data.get(key, filters[key]) for key in filters})
        context.update(
            {
                "filter_form": form,
                "filters": filters,
                "categories": Category.objects.active(),
                "current_category": Category.objects.active().filter(slug=category_slug).first()
                if category_slug
                else None,
                "query": form.cleaned_data.get("q", "") if form.is_bound else "",
                "sort_choices": ProductFilterForm.SORT_CHOICES,
                "current_sort": (form.cleaned_data.get("sort") if form.is_bound else "") or "newest",
                "recently_viewed": recently_viewed_products(self.request),
            }
        )
        return context


class ProductDetailView(DetailView):
    template_name = "products/detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return (
            Product.objects.visible()
            .select_related("category", "vendor__user")
            .prefetch_related("images", "variants")
        )

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        remember_product(request, self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        user = self.request.user
        reviews = product.reviews.filter(is_visible=True).select_related("user")
        context.update(
            {
                "reviews": reviews,
                "questions": product.questions.filter(is_public=True).select_related("user", "answered_by"),
                "related_products": Product.objects.visible()
                .filter(category=product.category)
                .exclude(pk=product.pk)
                .for_listing()
                .prefetch_related("variants")[:4],
                "review_form": ReviewForm(),
                "question_form": QuestionForm(),
                "recently_viewed": recently_viewed_products(self.request, exclude_id=product.pk)[:4],
                "rating_breakdown": _rating_breakdown(reviews, product.review_count),
            }
        )
        if user.is_authenticated:
            context["user_review"] = next((r for r in reviews if r.user_id == user.pk), None) or (
                product.reviews.filter(user=user).first()
            )
            context["in_wishlist"] = product.wishlisted_by.filter(user=user).exists()
            context["has_stock_alert"] = product.stock_alerts.filter(user=user, notified_at__isnull=True).exists()
        return context


def _rating_breakdown(reviews, total):
    counts = {star: 0 for star in range(1, 6)}
    for rating in reviews.values_list("rating", flat=True):
        counts[rating] += 1
    return [
        {"stars": star, "count": counts[star], "percent": round(counts[star] * 100 / total) if total else 0}
        for star in range(5, 0, -1)
    ]


# --------------------------------------------------------------------------
# Reviews
# --------------------------------------------------------------------------
@require_POST
@customer_required
def add_review(request, pk):
    product = get_object_or_404(Product.objects.visible(), pk=pk)
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.warning(request, "You have already reviewed this product. You can edit your review instead.")
        return redirect(product.get_absolute_url() + "#reviews")
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.is_verified_purchase = user_has_purchased(request.user, product)
        review.save()
        messages.success(request, "Thanks! Your review has been published.")
    else:
        for errors in form.errors.values():
            messages.error(request, errors[0])
    return redirect(product.get_absolute_url() + "#reviews")


@customer_required
def edit_review(request, pk):
    review = get_object_or_404(Review.objects.select_related("product"), pk=pk, user=request.user)
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your review has been updated.")
        return redirect(review.product.get_absolute_url() + "#reviews")
    return render(request, "products/review_form.html", {"form": form, "review": review, "product": review.product})


@require_POST
@customer_required
def delete_review(request, pk):
    review = get_object_or_404(Review.objects.select_related("product"), pk=pk, user=request.user)
    product = review.product
    review.delete()
    messages.success(request, "Your review has been deleted.")
    return redirect(product.get_absolute_url() + "#reviews")


# --------------------------------------------------------------------------
# Questions & stock alerts
# --------------------------------------------------------------------------
@require_POST
@customer_required
def ask_question(request, pk):
    product = get_object_or_404(Product.objects.visible(), pk=pk)
    form = QuestionForm(request.POST)
    if form.is_valid():
        ProductQuestion.objects.create(product=product, user=request.user, question=form.cleaned_data["question"])
        messages.success(request, "Your question has been sent to the seller.")
    else:
        messages.error(request, form.errors["question"][0])
    return redirect(product.get_absolute_url() + "#questions")


@require_POST
@customer_required
def stock_alert(request, pk):
    product = get_object_or_404(Product.objects.visible(), pk=pk)
    if product.is_in_stock:
        messages.info(request, f"{product.name} is in stock now.")
    else:
        _, created = subscribe_stock_alert(request.user, product)
        if created:
            messages.success(request, f"We'll email you when {product.name} is back in stock.")
        else:
            messages.info(request, "You're already subscribed to an alert for this product.")
    return redirect(product.get_absolute_url())
