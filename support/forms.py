from django import forms

from .models import SupportTicket


class TicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["subject", "order", "message"]
        labels = {"order": "Related order (optional)"}
        widgets = {"message": forms.Textarea(attrs={"rows": 6, "maxlength": 5000})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the user's own orders can be attached.
        self.fields["order"].queryset = user.orders.order_by("-created_at")
        self.fields["order"].label_from_instance = lambda o: f"{o.order_number} - {o.created_at:%b %d, %Y}"
        self.fields["order"].required = False

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please describe the issue in at least 10 characters.")
        return message


class ReplyForm(forms.Form):
    body = forms.CharField(label="Reply", max_length=5000, widget=forms.Textarea(attrs={"rows": 4}))


class StaffReplyForm(forms.Form):
    body = forms.CharField(label="Reply to customer", required=False, max_length=5000,
                           widget=forms.Textarea(attrs={"rows": 4}))
    status = forms.ChoiceField(label="Status", required=False)

    def __init__(self, *args, ticket, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = ticket.STAFF_TRANSITIONS.get(ticket.status, set())
        choices = [("", f"Keep as {ticket.get_status_display()}")]
        choices += [c for c in SupportTicket.Status.choices if c[0] in allowed]
        self.fields["status"].choices = choices
