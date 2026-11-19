from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from core.emails import absolute_url, send_templated_email

from .models import SupportTicket, TicketMessage


class TicketError(Exception):
    pass


def _staff_emails():
    User = get_user_model()
    return list(
        User.objects.filter(Q(is_superuser=True) | Q(role="admin"), is_active=True, is_staff=True).values_list(
            "email", flat=True
        )
    )


def _notify_customer(ticket, template, extra=None):
    url = absolute_url(reverse("support:ticket_detail", kwargs={"pk": ticket.pk}))
    context = {"ticket": ticket, "url": url, **(extra or {})}
    transaction.on_commit(lambda: send_templated_email(template, context, [ticket.user.email]))


@transaction.atomic
def open_ticket(user, subject, message, order=None):
    ticket = SupportTicket.objects.create(user=user, subject=subject, message=message, order=order)
    _notify_customer(ticket, "ticket_created")
    staff_url = absolute_url(reverse("support:staff_ticket_detail", kwargs={"pk": ticket.pk}))
    transaction.on_commit(
        lambda: send_templated_email("ticket_staff_alert", {"ticket": ticket, "url": staff_url}, _staff_emails())
    )
    return ticket


@transaction.atomic
def add_customer_reply(ticket, user, body):
    if ticket.user_id != user.pk:
        raise TicketError("You cannot reply to this ticket.")
    if ticket.is_closed:
        raise TicketError("This ticket is closed. Please open a new ticket.")
    message = TicketMessage.objects.create(ticket=ticket, author=user, body=body)
    fields = ["updated_at"]
    if ticket.status == SupportTicket.Status.RESOLVED:
        ticket.status = SupportTicket.Status.OPEN
        message.status_change = SupportTicket.Status.OPEN
        message.save(update_fields=["status_change"])
        fields.append("status")
    ticket.save(update_fields=fields)
    return message


@transaction.atomic
def customer_close(ticket, user):
    if ticket.user_id != user.pk:
        raise TicketError("You cannot close this ticket.")
    if ticket.is_closed:
        return ticket
    ticket.status = SupportTicket.Status.CLOSED
    ticket.save(update_fields=["status", "updated_at"])
    TicketMessage.objects.create(ticket=ticket, author=user, status_change=SupportTicket.Status.CLOSED)
    return ticket


@transaction.atomic
def staff_respond(ticket, staff_user, body="", new_status=""):
    if not body and not new_status:
        raise TicketError("Write a reply or choose a new status.")
    if new_status and new_status != ticket.status and not ticket.staff_can_transition_to(new_status):
        raise TicketError(
            f"Cannot move a ticket from {ticket.get_status_display()} to {SupportTicket.Status(new_status).label}."
        )
    status_change = new_status if new_status and new_status != ticket.status else ""
    message = TicketMessage.objects.create(
        ticket=ticket, author=staff_user, body=body, is_staff_reply=True, status_change=status_change
    )
    if status_change:
        ticket.status = status_change
    ticket.save(update_fields=["status", "updated_at"])
    _notify_customer(ticket, "ticket_updated", {"message": message})
    return message
