from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("support/tickets/", views.ticket_list, name="ticket_list"),
    path("support/tickets/new/", views.ticket_create, name="ticket_create"),
    path("support/tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path("support/tickets/<int:pk>/close/", views.ticket_close, name="ticket_close"),
    path("staff/tickets/", views.staff_ticket_list, name="staff_ticket_list"),
    path("staff/tickets/<int:pk>/", views.staff_ticket_detail, name="staff_ticket_detail"),
]
