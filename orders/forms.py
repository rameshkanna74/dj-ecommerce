from django import forms

from .models import OrderItem
from .payments import available_payment_methods


class CouponApplyForm(forms.Form):
    code = forms.CharField(
        label="Coupon code", max_length=50, widget=forms.TextInput(attrs={"placeholder": "e.g. WELCOME10"})
    )

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    phone = forms.RegexField(
        regex=r"^\+?[0-9 ()\-]{7,20}$",
        max_length=20,
        error_messages={"invalid": "Enter a valid phone number."},
        widget=forms.TextInput(attrs={"autocomplete": "tel"}),
    )
    address = forms.CharField(
        label="Street address", max_length=500, widget=forms.Textarea(attrs={"rows": 2, "autocomplete": "street-address"})
    )
    city = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"autocomplete": "address-level2"}))
    state = forms.CharField(
        max_length=100, required=False, label="State / region",
        widget=forms.TextInput(attrs={"autocomplete": "address-level1"}),
    )
    postal_code = forms.CharField(
        max_length=20, label="ZIP / postal code", widget=forms.TextInput(attrs={"autocomplete": "postal-code"})
    )
    country = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"autocomplete": "country-name"}))
    payment_method = forms.ChoiceField(widget=forms.RadioSelect)
    customer_note = forms.CharField(
        required=False, max_length=500, label="Delivery note (optional)", widget=forms.Textarea(attrs={"rows": 2})
    )
    save_address = forms.BooleanField(required=False, initial=True, label="Save as my default address")
    checkout_token = forms.CharField(widget=forms.HiddenInput, max_length=64)

    SHIPPING_FIELDS = ["full_name", "phone", "address", "city", "state", "postal_code", "country"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        methods = available_payment_methods()
        self.fields["payment_method"].choices = methods
        if methods:
            self.fields["payment_method"].initial = methods[0][0]

    def clean_full_name(self):
        return " ".join(self.cleaned_data["full_name"].split())

    def shipping_data(self):
        return {field: self.cleaned_data.get(field, "") for field in self.SHIPPING_FIELDS}


class OrderItemStatusForm(forms.Form):
    status = forms.ChoiceField(choices=OrderItem.Status.choices)
    tracking_number = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        if item is not None:
            allowed = item.allowed_next_statuses()
            self.fields["status"].choices = [c for c in OrderItem.Status.choices if c[0] in allowed]
            self.fields["tracking_number"].initial = item.tracking_number


class CancelOrderForm(forms.Form):
    reason = forms.CharField(
        required=False, max_length=300, label="Reason (optional)", widget=forms.Textarea(attrs={"rows": 2})
    )
