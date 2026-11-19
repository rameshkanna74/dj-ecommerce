from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_view, name="view"),
    path("add/<int:product_id>/", views.add_to_cart, name="add"),
    path("items/<int:item_id>/update/", views.update_cart_quantity, name="update"),
    path("items/<int:item_id>/remove/", views.remove_from_cart, name="remove"),
    path("items/<int:item_id>/toggle-save/", views.toggle_save_for_later, name="toggle_save"),
]
