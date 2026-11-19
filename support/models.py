from django.conf import settings
from django.db import models
from django.urls import reverse

from orders.models import Order


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    STATUS_CHOICES = Status.choices

    # Workflow: Open -> In Progress -> Resolved -> Closed. Staff may reopen.
    STAFF_TRANSITIONS = {
        Status.OPEN: {Status.IN_PROGRESS, Status.RESOLVED, Status.CLOSED},
        Status.IN_PROGRESS: {Status.OPEN, Status.RESOLVED, Status.CLOSED},
        Status.RESOLVED: {Status.IN_PROGRESS, Status.CLOSED},
        Status.CLOSED: {Status.OPEN},
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets")
    subject = models.CharField(max_length=200)
    message = models.TextField()
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-updated_at"]), models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"Ticket #{self.id}: {self.subject}"

    def get_absolute_url(self):
        return reverse("support:ticket_detail", kwargs={"pk": self.pk})

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED

    def staff_can_transition_to(self, status):
        return status in self.STAFF_TRANSITIONS.get(self.status, set())


class TicketMessage(models.Model):
    """A reply or a status event in a ticket's history."""

    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    body = models.TextField(blank=True)
    is_staff_reply = models.BooleanField(default=False)
    status_change = models.CharField(max_length=20, choices=SupportTicket.Status.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Message on ticket #{self.ticket_id}"
