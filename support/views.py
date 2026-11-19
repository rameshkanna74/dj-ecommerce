from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import admin_required

from . import services
from .forms import ReplyForm, StaffReplyForm, TicketForm
from .models import SupportTicket


@login_required
def ticket_list(request):
    tickets = (
        SupportTicket.objects.filter(user=request.user)
        .select_related("order")
        .annotate(reply_count=Count("messages", filter=Q(messages__is_staff_reply=True)))
        .order_by("-updated_at")
    )
    page = Paginator(tickets, 10).get_page(request.GET.get("page"))
    return render(request, "support/ticket_list.html", {"page_obj": page, "tickets": page.object_list})


@login_required
def ticket_create(request):
    form = TicketForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        ticket = services.open_ticket(
            request.user, form.cleaned_data["subject"], form.cleaned_data["message"], form.cleaned_data["order"]
        )
        messages.success(request, f"Ticket #{ticket.pk} created. Our team will reply soon.")
        return redirect(ticket.get_absolute_url())
    initial_order = request.GET.get("order")
    if request.method == "GET" and initial_order:
        match = request.user.orders.filter(order_number=initial_order).first()
        if match:
            form.initial["order"] = match.pk
    return render(request, "support/ticket_form.html", {"form": form})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(SupportTicket.objects.select_related("order"), pk=pk, user=request.user)
    form = ReplyForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                services.add_customer_reply(ticket, request.user, form.cleaned_data["body"])
                messages.success(request, "Your reply has been sent.")
                return redirect(ticket.get_absolute_url())
            except services.TicketError as exc:
                messages.error(request, str(exc))
    return render(
        request,
        "support/ticket_detail.html",
        {"ticket": ticket, "history": ticket.messages.select_related("author"), "form": form},
    )


@require_POST
@login_required
def ticket_close(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk, user=request.user)
    services.customer_close(ticket, request.user)
    messages.success(request, "Ticket closed.")
    return redirect(ticket.get_absolute_url())


@admin_required
def staff_ticket_list(request):
    tickets = SupportTicket.objects.select_related("user", "order").order_by("-updated_at")
    status = request.GET.get("status", "")
    if status in SupportTicket.Status.values:
        tickets = tickets.filter(status=status)
    query = request.GET.get("q", "").strip()
    if query:
        tickets = tickets.filter(
            Q(subject__icontains=query) | Q(user__username__icontains=query) | Q(user__email__icontains=query)
        )
    counts = dict(SupportTicket.objects.values_list("status").annotate(n=Count("id")).order_by())
    page = Paginator(tickets, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "support/staff_ticket_list.html",
        {
            "page_obj": page,
            "tickets": page.object_list,
            "status_filter": status,
            "query": query,
            "status_counts": [(v, label, counts.get(v, 0)) for v, label in SupportTicket.Status.choices],
        },
    )


@admin_required
def staff_ticket_detail(request, pk):
    ticket = get_object_or_404(SupportTicket.objects.select_related("user", "order"), pk=pk)
    form = StaffReplyForm(request.POST or None, ticket=ticket)
    if request.method == "POST" and form.is_valid():
        try:
            services.staff_respond(ticket, request.user, form.cleaned_data["body"].strip(), form.cleaned_data["status"])
            messages.success(request, "Ticket updated and the customer has been notified.")
            return redirect("support:staff_ticket_detail", pk=ticket.pk)
        except services.TicketError as exc:
            messages.error(request, str(exc))
    return render(
        request,
        "support/staff_ticket_detail.html",
        {"ticket": ticket, "history": ticket.messages.select_related("author"), "form": form},
    )
