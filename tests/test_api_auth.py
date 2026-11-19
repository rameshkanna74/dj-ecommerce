import re

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import CustomUser, VendorProfile

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Vivid-Orchard-42"


def register_payload(**extra):
    data = {"username": "newbie", "first_name": "New", "last_name": "User", "email": "newbie@example.com",
            "password": NEW_PASSWORD}
    data.update(extra)
    return data


def bearer(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class TestRegistration:
    def test_customer_registration_returns_tokens(self):
        response = APIClient().post(reverse("api:register-customer"), register_payload(), format="json")
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["role"] == "customer" and body["access"] and body["refresh"]
        assert bearer(body["access"]).get(reverse("api:me")).json()["username"] == "newbie"

    def test_role_and_staff_flags_cannot_be_injected(self):
        APIClient().post(reverse("api:register-customer"),
                         register_payload(role="admin", is_staff=True, is_superuser=True), format="json")
        user = CustomUser.objects.get(username="newbie")
        assert user.role == "customer" and not user.is_staff and not user.is_superuser

    def test_validation_errors_are_field_keyed(self, customer):
        response = APIClient().post(reverse("api:register-customer"),
                                    register_payload(email="ALICE@example.com", password="123"), format="json")
        assert response.status_code == 400
        assert "email" in response.json() and "password" in response.json()

    def test_vendor_registration_is_pending(self):
        payload = register_payload(
            username="maker", email="maker@example.com", business_name="Maker Co", business_email="m@example.com",
            business_phone="555", business_address="1 Rd", business_city="X", business_state="Y",
            business_zip_code="1", accept_terms=True,
        )
        response = APIClient().post(reverse("api:register-vendor"), payload, format="json")
        assert response.status_code == 201
        assert VendorProfile.objects.get().approval_status == "pending"
        assert response.json()["user"]["vendor"]["approval_status"] == "pending"


class TestTokens:
    def test_login_with_email_refresh_and_logout(self, customer):
        client = APIClient()
        response = client.post(reverse("api:token"), {"username": "alice@example.com", "password": PASSWORD},
                               format="json")
        assert response.status_code == 200
        tokens = response.json()
        assert tokens["user"]["email"] == "alice@example.com"

        refreshed = client.post(reverse("api:token-refresh"), {"refresh": tokens["refresh"]}, format="json")
        assert refreshed.status_code == 200
        new_refresh = refreshed.json()["refresh"]
        # Rotation blacklists the old refresh token.
        assert client.post(reverse("api:token-refresh"), {"refresh": tokens["refresh"]},
                           format="json").status_code == 401

        assert client.post(reverse("api:logout"), {"refresh": new_refresh}, format="json").status_code == 205
        assert client.post(reverse("api:token-refresh"), {"refresh": new_refresh}, format="json").status_code == 401

    def test_bad_credentials_and_inactive_user(self, customer):
        client = APIClient()
        assert client.post(reverse("api:token"), {"username": "alice", "password": "wrong"},
                           format="json").status_code == 401
        customer.is_active = False
        customer.save()
        assert client.post(reverse("api:token"), {"username": "alice", "password": PASSWORD},
                           format="json").status_code == 401

    def test_invalid_bearer_token_rejected(self):
        assert bearer("not-a-jwt").get(reverse("api:me")).status_code == 401

    def test_anonymous_gets_401(self):
        assert APIClient().get(reverse("api:me")).status_code == 401

    def test_auth_endpoints_are_throttled(self, customer):
        client = APIClient()
        codes = [client.post(reverse("api:token"), {"username": "alice", "password": "x"}, format="json").status_code
                 for _ in range(21)]
        assert codes[-1] == 429


class TestSessionAuth:
    def test_session_auth_enforces_csrf(self, customer, product):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="alice", password=PASSWORD)
        assert client.get(reverse("api:me")).status_code == 200
        response = client.post(reverse("api:cart-items"), {"product": product.pk}, format="json")
        assert response.status_code == 403 and "CSRF" in response.json()["detail"]


class TestMeAndPasswords:
    def test_update_profile_and_address(self, api, customer):
        response = api(customer).patch(
            reverse("api:me"),
            {"first_name": "Alicia", "role": "admin", "customer_profile": {"city": "Portland"}},
            format="json",
        )
        assert response.status_code == 200
        customer.refresh_from_db()
        assert customer.first_name == "Alicia" and customer.role == "customer"
        assert customer.customer_profile.city == "Portland"

    def test_duplicate_email_rejected(self, api, customer, other_customer):
        response = api(customer).patch(reverse("api:me"), {"email": other_customer.email}, format="json")
        assert response.status_code == 400

    def test_password_change(self, api, customer):
        client = api(customer)
        assert client.post(reverse("api:password-change"), {"old_password": "nope", "new_password": NEW_PASSWORD},
                           format="json").status_code == 400
        assert client.post(reverse("api:password-change"), {"old_password": PASSWORD, "new_password": NEW_PASSWORD},
                           format="json").status_code == 204
        customer.refresh_from_db()
        assert customer.check_password(NEW_PASSWORD)

    def test_password_reset_flow(self, customer, mailoutbox, settings):
        settings.CORECART_FRONTEND_URL = "https://app.example.com"
        client = APIClient()
        assert client.post(reverse("api:password-reset"), {"email": "ghost@example.com"},
                           format="json").status_code == 202
        assert mailoutbox == []
        assert client.post(reverse("api:password-reset"), {"email": customer.email}, format="json").status_code == 202
        match = re.search(r"https://app\.example\.com/reset-password\?uid=([^&]+)&token=(\S+)", mailoutbox[0].body)
        uid, token = match.groups()
        assert client.post(reverse("api:password-reset-confirm"),
                           {"uid": uid, "token": "bad", "new_password": NEW_PASSWORD}, format="json").status_code == 400
        assert client.post(reverse("api:password-reset-confirm"),
                           {"uid": uid, "token": token, "new_password": NEW_PASSWORD},
                           format="json").status_code == 204
        customer.refresh_from_db()
        assert customer.check_password(NEW_PASSWORD)


class TestWishlist:
    def test_add_list_move_remove(self, api, customer, product, make_product):
        client = api(customer)
        assert client.post(reverse("api:wishlist"), {"product": product.pk}, format="json").status_code == 201
        assert [p["slug"] for p in client.get(reverse("api:wishlist")).json()] == [product.slug]
        assert client.post(reverse("api:wishlist-move", args=[product.pk])).status_code == 204
        assert customer.cart_items.count() == 1 and customer.wishlist.products.count() == 0
        other = make_product(name="Other")
        client.post(reverse("api:wishlist"), {"product": other.pk}, format="json")
        assert client.delete(reverse("api:wishlist-item", args=[other.pk])).status_code == 204

    def test_vendor_forbidden(self, api, vendor):
        assert api(vendor.user).get(reverse("api:wishlist")).status_code == 403
