from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.forms import CustomerRegistrationForm, VendorRegistrationForm
from accounts.models import CustomerProfile, CustomUser, VendorProfile


def use_cookie_field():
    return serializers.BooleanField(
        required=False, default=False, write_only=True,
        help_text="Browser clients: return the refresh token as an httpOnly cookie instead of in the body.",
    )


def _form_errors(form):
    return {field: [e["message"] for e in errors] for field, errors in form.errors.get_json_data().items()}


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ["address", "city", "state", "zip_code", "country", "newsletter_subscribed", "email_notifications"]


class VendorSummarySerializer(serializers.ModelSerializer):
    approval_status_display = serializers.CharField(source="get_approval_status_display", read_only=True)

    class Meta:
        model = VendorProfile
        fields = ["id", "business_name", "store_slug", "approval_status", "approval_status_display",
                  "rejection_reason", "commission_rate", "created_at", "approved_at"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """The signed-in user. ``role``, ``username`` and flags are read-only."""

    customer_profile = CustomerProfileSerializer(required=False)
    vendor = VendorSummarySerializer(source="vendor_profile", read_only=True)
    is_platform_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "first_name", "last_name", "phone", "avatar", "role",
                  "is_platform_admin", "date_joined", "customer_profile", "vendor"]
        read_only_fields = ["id", "username", "role", "date_joined"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.is_customer:
            data.pop("customer_profile", None)
        if not instance.is_vendor:
            data.pop("vendor", None)
        return data

    def validate_email(self, value):
        value = value.strip().lower()
        if CustomUser.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("customer_profile", None)
        instance = super().update(instance, validated_data)
        if profile_data and instance.is_customer:
            profile = instance.customer_profile
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.save()
        return instance


class _FormBackedRegistrationSerializer(serializers.Serializer):
    """Delegates validation to the existing registration ModelForm so rules live in one place."""

    form_class = None

    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    use_cookie = use_cookie_field()

    def _form_data(self, attrs):
        data = {**attrs, "password1": attrs["password"], "password2": attrs["password"]}
        data.pop("password")
        data.pop("use_cookie", None)
        return data

    def validate(self, attrs):
        form = self.form_class(data=self._form_data(attrs))
        if not form.is_valid():
            errors = _form_errors(form)
            if "password2" in errors:
                errors["password"] = errors.pop("password2")
            raise serializers.ValidationError(errors)
        self._form = form
        return attrs

    def create(self, validated_data):
        return self._form.save()

    def to_representation(self, instance):
        return UserSerializer(instance, context=self.context).data


class CustomerRegistrationSerializer(_FormBackedRegistrationSerializer):
    form_class = CustomerRegistrationForm
    newsletter_subscribed = serializers.BooleanField(required=False, default=False)


class VendorRegistrationSerializer(_FormBackedRegistrationSerializer):
    form_class = VendorRegistrationForm

    business_name = serializers.CharField(max_length=200)
    business_description = serializers.CharField(required=False, allow_blank=True)
    business_email = serializers.EmailField()
    business_phone = serializers.CharField(max_length=20)
    business_address = serializers.CharField()
    business_city = serializers.CharField(max_length=100)
    business_state = serializers.CharField(max_length=100)
    business_zip_code = serializers.CharField(max_length=20)
    business_country = serializers.CharField(max_length=100, required=False, default="USA")
    tax_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    business_registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    accept_terms = serializers.BooleanField()


class TokenWithUserSerializer(TokenObtainPairSerializer):
    """Returns ``access``, ``refresh`` and the user. ``username`` may also be an email address."""

    use_cookie = use_cookie_field()

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        from django.conf import settings

        form = PasswordResetForm(data=self.validated_data)
        if form.is_valid():
            request = self.context["request"]
            form.save(
                request=request,
                use_https=request.is_secure(),
                subject_template_name="emails/password_reset_subject.txt",
                email_template_name="emails/password_reset_api_body.txt",
                extra_email_context={"frontend_url": settings.CORECART_FRONTEND_URL},
            )


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user = CustomUser.objects.get(pk=force_str(urlsafe_base64_decode(attrs["uid"])))
        except (CustomUser.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": ["This reset link is invalid or has expired."]})
        form = SetPasswordForm(user, {"new_password1": attrs["new_password"], "new_password2": attrs["new_password"]})
        if not form.is_valid():
            raise serializers.ValidationError({"new_password": _form_errors(form).get("new_password2", ["Invalid."])})
        self._form = form
        return attrs

    def save(self):
        return self._form.save()


class OptionalRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, help_text="Omit when using the httpOnly refresh cookie.")
