import pytest
from django.urls import reverse

from orders.models import Order
from support import services
from support.models import SupportTicket

pytestmark = pytest.mark.django_db


def create_ticket(client, **data):
    payload = {"subject": "Where is my parcel?", "message": "It has been a week since I ordered.", "order": ""}
    payload.update(data)
    return client.post(reverse("support:ticket_create"), payload)


def test_customer_creates_ticket_and_gets_email(customer_client, customer, admin_user, mailoutbox,
                                                django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = create_ticket(customer_client)
    ticket = SupportTicket.objects.get()
    assert response.status_code == 302 and response.url == ticket.get_absolute_url()
    assert ticket.user == customer and ticket.status == "open"
    recipients = {m.to[0] for m in mailoutbox}
    assert {customer.email, admin_user.email} <= recipients


def test_ticket_can_reference_only_own_orders(customer_client, customer, other_customer):
    foreign = Order.objects.create(user=other_customer, total_amount=1)
    response = create_ticket(customer_client, order=foreign.pk)
    assert response.status_code == 200
    assert not SupportTicket.objects.exists()
    own = Order.objects.create(user=customer, total_amount=1)
    create_ticket(customer_client, order=own.pk)
    assert SupportTicket.objects.get().order == own


def test_message_validation(customer_client):
    response = create_ticket(customer_client, message="short")
    assert response.status_code == 200 and not SupportTicket.objects.exists()


def test_customers_see_only_their_tickets(login, customer, other_customer, vendor):
    ticket = services.open_ticket(customer, "Help", "Please help me with my order")
    assert login(other_customer).get(ticket.get_absolute_url()).status_code == 404
    assert login(vendor.user).get(ticket.get_absolute_url()).status_code == 404
    assert login(vendor.user).get(reverse("support:staff_ticket_detail", args=[ticket.pk])).status_code == 403
    assert list(login(other_customer).get(reverse("support:ticket_list")).context["tickets"]) == []


def test_staff_reply_and_status_workflow(login, admin_user, customer, mailoutbox,
                                         django_capture_on_commit_callbacks):
    ticket = services.open_ticket(customer, "Help", "Please help me with my order")
    client = login(admin_user)
    url = reverse("support:staff_ticket_detail", args=[ticket.pk])
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"body": "Looking into it.", "status": "in_progress"})
    ticket.refresh_from_db()
    assert ticket.status == "in_progress"
    assert ticket.messages.get().is_staff_reply
    assert any("Update on support ticket" in m.subject for m in mailoutbox)

    client.post(url, {"body": "", "status": "resolved"})
    ticket.refresh_from_db()
    assert ticket.status == "resolved"
    with pytest.raises(services.TicketError):
        services.staff_respond(ticket, admin_user, "", "open")


def test_customer_reply_reopens_resolved_ticket_and_close(login, customer, admin_user):
    ticket = services.open_ticket(customer, "Help", "Please help me with my order")
    services.staff_respond(ticket, admin_user, "Fixed", "resolved")
    client = login(customer)
    client.post(ticket.get_absolute_url(), {"body": "Still broken, sorry."})
    ticket.refresh_from_db()
    assert ticket.status == "open"
    client.post(reverse("support:ticket_close", args=[ticket.pk]))
    ticket.refresh_from_db()
    assert ticket.status == "closed"
    client.post(ticket.get_absolute_url(), {"body": "One more thing"})
    assert ticket.messages.filter(body="One more thing").count() == 0


def test_history_rendered(login, customer, admin_user):
    ticket = services.open_ticket(customer, "Help", "Please help me with my order")
    services.staff_respond(ticket, admin_user, "We have shipped a replacement.", "resolved")
    html = login(customer).get(ticket.get_absolute_url()).content.decode()
    assert "We have shipped a replacement." in html and "CoreCart Support" in html and "Resolved" in html


def test_staff_queue_filters(login, admin_user, customer):
    services.open_ticket(customer, "Billing question", "Please explain this charge to me")
    response = login(admin_user).get(reverse("support:staff_ticket_list"), {"status": "closed"})
    assert list(response.context["tickets"]) == []
    response = login(admin_user).get(reverse("support:staff_ticket_list"), {"q": "billing"})
    assert len(response.context["tickets"]) == 1
