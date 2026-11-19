"""Root URL configuration for CoreCart."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "CoreCart administration"
admin.site.site_title = "CoreCart admin"
admin.site.index_title = "Marketplace management"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include("config.api_urls")),
    path("cart/", include("cart.urls")),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("products.urls")),
    path("", include("orders.urls")),
    path("", include("analytics.urls")),
    path("", include("support.urls")),
]

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
