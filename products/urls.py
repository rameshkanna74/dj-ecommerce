from django.urls import path

from . import vendor_views, views

app_name = "products"

urlpatterns = [
    # Public catalogue
    path("products/", views.ProductListView.as_view(), name="list"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="detail"),
    path("products/<int:pk>/reviews/", views.add_review, name="add_review"),
    path("products/<int:pk>/questions/", views.ask_question, name="ask_question"),
    path("products/<int:pk>/stock-alert/", views.stock_alert, name="stock_alert"),
    path("reviews/<int:pk>/edit/", views.edit_review, name="edit_review"),
    path("reviews/<int:pk>/delete/", views.delete_review, name="delete_review"),
    # Vendor catalogue management
    path("vendor/products/", vendor_views.VendorProductListView.as_view(), name="vendor_list"),
    path("vendor/products/new/", vendor_views.product_create, name="create"),
    path("vendor/products/<int:pk>/edit/", vendor_views.product_update, name="update"),
    path("vendor/products/<int:pk>/delete/", vendor_views.ProductDeleteView.as_view(), name="delete"),
    path("vendor/inventory/", vendor_views.inventory, name="inventory"),
    path("vendor/inventory/<int:pk>/", vendor_views.update_stock, name="update_stock"),
    path("vendor/reviews/", vendor_views.vendor_reviews, name="vendor_reviews"),
    path("vendor/questions/", vendor_views.vendor_questions, name="vendor_questions"),
    path("vendor/questions/<int:pk>/answer/", vendor_views.answer_question, name="answer_question"),
]
