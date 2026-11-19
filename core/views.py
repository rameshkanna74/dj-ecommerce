from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render

from products.models import Category, Product
from products.views import recently_viewed_products


def home(request):
    visible = Product.objects.visible().for_listing().prefetch_related("variants")
    featured = list(visible.filter(is_featured=True).order_by("-created_at")[:8])
    if not featured:
        # Fall back to the best-rated products so the section is never empty.
        featured = list(visible.order_by("-average_rating", "-review_count", "-created_at")[:8])

    best_sellers = [p for p in visible.with_units_sold().order_by("-units_sold", "-created_at")[:4] if p.units_sold]

    categories = (
        Category.objects.active()
        .annotate(
            product_count=Count(
                "products",
                filter=Q(products__is_active=True)
                & (Q(products__vendor__isnull=True) | Q(products__vendor__approval_status="approved")),
            )
        )
        .filter(product_count__gt=0)
        .order_by("-product_count", "name")[:6]
    )

    return render(
        request,
        "core/home.html",
        {
            "featured_products": featured,
            "new_arrivals": visible.order_by("-created_at")[:8],
            "best_sellers": best_sellers,
            "featured_categories": categories,
            "recently_viewed": recently_viewed_products(request)[:4],
        },
    )


def about(request):
    return render(request, "core/about.html")


def _is_api(request):
    return request.path.startswith("/api/")


def error_403(request, exception=None):
    if _is_api(request):
        return JsonResponse({"detail": "You do not have permission to perform this action.",
                             "code": "permission_denied"}, status=403)
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    if _is_api(request):
        return JsonResponse({"detail": "Not found.", "code": "not_found"}, status=404)
    return render(request, "errors/404.html", status=404)


def error_500(request):
    if _is_api(request):
        return JsonResponse({"detail": "A server error occurred.", "code": "server_error"}, status=500)
    return render(request, "errors/500.html", status=500)
