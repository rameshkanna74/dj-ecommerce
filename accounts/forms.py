from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction

from core.utils import unique_slugify

from .models import CustomerProfile, CustomUser, VendorProfile


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )


class _BaseRegistrationForm(UserCreationForm):
    """Common user fields. The role is assigned by subclasses, never by the browser."""

    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={"autocomplete": "tel"}))

    role = None

    class Meta:
        model = CustomUser
        fields = ["username", "first_name", "last_name", "email", "phone"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def _build_user(self):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        user.role = self.role
        return user


class CustomerRegistrationForm(_BaseRegistrationForm):
    role = CustomUser.Role.CUSTOMER

    newsletter_subscribed = forms.BooleanField(
        required=False, initial=False, label="Send me product news and offers"
    )

    @transaction.atomic
    def save(self, commit=True):
        user = self._build_user()
        user.save()
        # The post_save signal creates the profile; update preferences here.
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.newsletter_subscribed = self.cleaned_data.get("newsletter_subscribed", False)
        profile.save(update_fields=["newsletter_subscribed", "updated_at"])
        return user


class VendorRegistrationForm(_BaseRegistrationForm):
    role = CustomUser.Role.VENDOR

    business_name = forms.CharField(max_length=200)
    business_description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    business_email = forms.EmailField()
    business_phone = forms.CharField(max_length=20)
    business_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    business_city = forms.CharField(max_length=100)
    business_state = forms.CharField(max_length=100)
    business_zip_code = forms.CharField(max_length=20, label="ZIP / postal code")
    business_country = forms.CharField(max_length=100, initial="USA")
    tax_id = forms.CharField(max_length=50, required=False, label="Tax ID / EIN")
    business_registration_number = forms.CharField(max_length=100, required=False)
    accept_terms = forms.BooleanField(required=True, label="I accept the vendor terms and conditions")

    BUSINESS_FIELDS = [
        "business_name",
        "business_description",
        "business_email",
        "business_phone",
        "business_address",
        "business_city",
        "business_state",
        "business_zip_code",
        "business_country",
        "tax_id",
        "business_registration_number",
    ]

    def clean_business_name(self):
        name = self.cleaned_data["business_name"].strip()
        if VendorProfile.objects.filter(business_name__iexact=name).exists():
            raise forms.ValidationError("This business name is already registered.")
        return name

    @transaction.atomic
    def save(self, commit=True):
        user = self._build_user()
        user.save()
        profile = VendorProfile(
            user=user,
            approval_status=VendorProfile.Approval.PENDING,
            **{field: self.cleaned_data.get(field, "") for field in self.BUSINESS_FIELDS},
        )
        profile.store_slug = unique_slugify(profile, profile.business_name, slug_field="store_slug")
        profile.save()
        return user


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "email", "phone", "avatar"]
        widgets = {"avatar": forms.ClearableFileInput(attrs={"accept": "image/*"})}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already in use.")
        return email


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = [
            "address",
            "city",
            "state",
            "zip_code",
            "country",
            "newsletter_subscribed",
            "email_notifications",
        ]
        labels = {"address": "Street address", "zip_code": "ZIP / postal code"}
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}


class VendorProfileForm(forms.ModelForm):
    """Store settings a vendor may edit. Approval, commission and slug are admin-only."""

    class Meta:
        model = VendorProfile
        fields = [
            "business_name",
            "business_description",
            "business_logo",
            "business_banner",
            "business_email",
            "business_phone",
            "business_address",
            "business_city",
            "business_state",
            "business_zip_code",
            "business_country",
            "tax_id",
            "business_registration_number",
        ]
        widgets = {
            "business_description": forms.Textarea(attrs={"rows": 4}),
            "business_address": forms.Textarea(attrs={"rows": 2}),
            "business_logo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "business_banner": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def clean_business_name(self):
        name = self.cleaned_data["business_name"].strip()
        if VendorProfile.objects.filter(business_name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This business name is already registered.")
        return name
