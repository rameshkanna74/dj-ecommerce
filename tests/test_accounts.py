import pytest
from django.urls import reverse

from accounts.models import CustomerProfile, CustomUser, VendorProfile, Wishlist

from .conftest import PASSWORD, make_user

pytestmark = pytest.mark.django_db

REG_PASSWORD = "Vivid-Orchard-42"


def customer_payload(**overrides):
    data = {
        "username": "newbie",
        "first_name": "New",
        "last_name": "Customer",
        "email": "newbie@example.com",
        "phone": "",
        "password1": REG_PASSWORD,
        "password2": REG_PASSWORD,
    }
    data.update(overrides)
    return data


def vendor_payload(**overrides):
    data = customer_payload(username="maker", email="maker@example.com")
    data.update(
        {
            "business_name": "Maker & Co",
            "business_description": "Handmade",
            "business_email": "hello@maker.example.com",
            "business_phone": "5550199",
            "business_address": "2 Mill Rd",
            "business_city": "Leeds",
            "business_state": "WY",
            "business_zip_code": "82001",
            "business_country": "USA",
            "accept_terms": "on",
        }
    )
    data.update(overrides)
    return data


class TestModels:
    def test_default_role_and_related_records(self):
        user = make_user("plain")
        assert user.role == CustomUser.Role.CUSTOMER
        assert user.is_customer and not user.is_vendor and not user.is_admin_role
        assert Wishlist.objects.filter(user=user).exists()
        assert CustomerProfile.objects.filter(user=user).exists()
        assert str(user) == "plain (Customer)"

    def test_vendor_user_has_no_customer_profile(self, vendor):
        assert not CustomerProfile.objects.filter(user=vendor.user).exists()

    def test_dashboard_urls_use_named_routes(self, vendor, admin_user):
        customer = make_user("cust")
        assert customer.get_dashboard_url() == reverse("accounts:customer_dashboard")
        assert vendor.user.get_dashboard_url() == reverse("accounts:vendor_dashboard")
        assert admin_user.get_dashboard_url() == reverse("analytics:admin_dashboard")

    def test_platform_admin_requires_superuser_or_staff_admin_role(self, admin_user):
        assert admin_user.is_platform_admin
        assert not make_user("adm", role=CustomUser.Role.ADMIN).is_platform_admin
        assert make_user("adm2", role=CustomUser.Role.ADMIN, is_staff=True).is_platform_admin

    def test_vendor_can_sell_only_when_approved_and_active(self, vendor, pending_vendor):
        assert vendor.can_sell
        assert not pending_vendor.can_sell
        vendor.user.is_active = False
        vendor.user.save()
        assert not vendor.can_sell

    def test_approval_workflow_methods(self, pending_vendor, admin_user):
        pending_vendor.approve(by=admin_user)
        pending_vendor.refresh_from_db()
        assert pending_vendor.is_approved and pending_vendor.approved_by == admin_user
        assert pending_vendor.approved_at is not None
        pending_vendor.reject(by=admin_user, reason="Incomplete documents")
        pending_vendor.refresh_from_db()
        assert pending_vendor.approval_status == "rejected"
        assert pending_vendor.approved_at is None
        assert pending_vendor.rejection_reason == "Incomplete documents"


class TestRegistration:
    def test_customer_registration_logs_in_and_creates_profile(self, client):
        response = client.post(reverse("accounts:customer_register"), customer_payload())
        assert response.status_code == 302
        user = CustomUser.objects.get(username="newbie")
        assert user.role == "customer"
        assert user.customer_profile is not None
        assert client.session["_auth_user_id"] == str(user.pk)

    def test_role_cannot_be_injected_from_the_browser(self, client):
        client.post(reverse("accounts:customer_register"), customer_payload(role="admin", is_staff="on"))
        user = CustomUser.objects.get(username="newbie")
        assert user.role == "customer"
        assert not user.is_staff and not user.is_superuser

    def test_duplicate_email_is_rejected_case_insensitively(self, client, customer):
        response = client.post(reverse("accounts:customer_register"), customer_payload(email="ALICE@example.com"))
        assert response.status_code == 200
        assert "already exists" in response.content.decode()

    def test_weak_password_rejected(self, client):
        response = client.post(
            reverse("accounts:customer_register"), customer_payload(password1="12345678", password2="12345678")
        )
        assert response.status_code == 200
        assert not CustomUser.objects.filter(username="newbie").exists()

    def test_vendor_registration_creates_pending_profile(self, client):
        response = client.post(reverse("accounts:vendor_register"), vendor_payload())
        assert response.status_code == 302
        assert response.url == reverse("accounts:vendor_pending")
        profile = VendorProfile.objects.get(user__username="maker")
        assert profile.approval_status == "pending"
        assert profile.store_slug == "maker-co"
        assert profile.user.role == "vendor"

    def test_vendor_store_slug_is_collision_safe(self, client, vendor):
        vendor.store_slug = "maker-co"
        vendor.save()
        client.post(reverse("accounts:vendor_register"), vendor_payload())
        assert VendorProfile.objects.get(user__username="maker").store_slug == "maker-co-2"

    def test_vendor_registration_requires_terms(self, client):
        response = client.post(reverse("accounts:vendor_register"), vendor_payload(accept_terms=""))
        assert response.status_code == 200
        assert not CustomUser.objects.filter(username="maker").exists()


class TestAuthentication:
    def test_login_with_username_and_email(self, client, customer):
        assert client.post(reverse("accounts:login"), {"username": "alice", "password": PASSWORD}).status_code == 302
        client.logout()
        response = client.post(reverse("accounts:login"), {"username": "ALICE@example.com", "password": PASSWORD})
        assert response.status_code == 302

    def test_inactive_user_cannot_login(self, client, customer):
        customer.is_active = False
        customer.save()
        response = client.post(reverse("accounts:login"), {"username": "alice", "password": PASSWORD})
        assert response.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_login_ignores_unsafe_next(self, client, customer):
        response = client.post(
            reverse("accounts:login"), {"username": "alice", "password": PASSWORD, "next": "https://evil.example/"}
        )
        assert response.status_code == 302
        assert "evil.example" not in response.url

    def test_logout_requires_post(self, customer_client):
        assert customer_client.get(reverse("accounts:logout")).status_code == 405
        response = customer_client.post(reverse("accounts:logout"))
        assert response.status_code == 302
        assert "_auth_user_id" not in customer_client.session

    def test_password_reset_sends_email_with_valid_link(self, client, customer, mailoutbox):
        response = client.post(reverse("accounts:password_reset"), {"email": customer.email})
        assert response.status_code == 302
        assert len(mailoutbox) == 1
        assert mailoutbox[0].subject == "Reset your CoreCart password"
        link = next(line for line in mailoutbox[0].body.splitlines() if "/password-reset/" in line)
        path = link.split("testserver", 1)[1]
        confirm = client.get(path, follow=True)
        assert confirm.status_code == 200
        assert confirm.context["validlink"] is True
        done = client.post(
            confirm.redirect_chain[-1][0], {"new_password1": "Another-Str0ng-1", "new_password2": "Another-Str0ng-1"}
        )
        assert done.status_code == 302
        customer.refresh_from_db()
        assert customer.check_password("Another-Str0ng-1")

    def test_password_reset_unknown_email_does_not_leak(self, client, mailoutbox):
        response = client.post(reverse("accounts:password_reset"), {"email": "ghost@example.com"})
        assert response.status_code == 302
        assert mailoutbox == []

    def test_password_change(self, customer_client, customer):
        response = customer_client.post(
            reverse("accounts:password_change"),
            {"old_password": PASSWORD, "new_password1": "Fresh-Garden-77", "new_password2": "Fresh-Garden-77"},
        )
        assert response.status_code == 302
        customer.refresh_from_db()
        assert customer.check_password("Fresh-Garden-77")


class TestRolePermissions:
    @pytest.mark.parametrize(
        "url_name",
        ["accounts:vendor_dashboard", "accounts:vendor_profile", "products:vendor_list", "products:create",
         "orders:vendor_order_list", "analytics:vendor_dashboard", "products:inventory"],
    )
    def test_customer_cannot_access_vendor_pages(self, customer_client, url_name):
        assert customer_client.get(reverse(url_name)).status_code == 403

    @pytest.mark.parametrize("url_name", ["analytics:admin_dashboard", "support:staff_ticket_list",
                                          "analytics:export_orders"])
    def test_non_admins_cannot_access_admin_pages(self, customer_client, vendor, login, url_name):
        assert customer_client.get(reverse(url_name)).status_code == 403
        assert login(vendor.user).get(reverse(url_name)).status_code == 403

    def test_anonymous_redirected_to_login(self, client):
        response = client.get(reverse("accounts:customer_dashboard"))
        assert response.status_code == 302
        assert response.url.startswith(reverse("accounts:login"))

    def test_pending_vendor_redirected_to_pending_page(self, login, pending_vendor):
        client = login(pending_vendor.user)
        response = client.get(reverse("products:create"))
        assert response.status_code == 302
        assert response.url == reverse("accounts:vendor_pending")
        assert client.get(reverse("accounts:vendor_pending")).status_code == 200

    def test_vendor_cannot_use_customer_pages(self, vendor_client):
        assert vendor_client.get(reverse("cart:view")).status_code == 403
        assert vendor_client.get(reverse("orders:checkout")).status_code == 403

    def test_dashboard_redirects_by_role(self, login, customer, vendor, admin_user, pending_vendor):
        assert login(customer).get(reverse("accounts:dashboard")).url == reverse("accounts:customer_dashboard")
        assert login(vendor.user).get(reverse("accounts:dashboard")).url == reverse("accounts:vendor_dashboard")
        assert login(pending_vendor.user).get(reverse("accounts:dashboard")).url == reverse("accounts:vendor_pending")
        assert login(admin_user).get(reverse("accounts:dashboard")).url == reverse("analytics:admin_dashboard")


class TestProfiles:
    def test_customer_profile_update(self, customer_client, customer):
        response = customer_client.post(
            reverse("accounts:customer_profile"),
            {
                "first_name": "Alicia", "last_name": "Smith", "email": "alicia@example.com", "phone": "555",
                "address": "1 Road", "city": "Town", "state": "", "zip_code": "123", "country": "USA",
                "email_notifications": "on",
            },
        )
        assert response.status_code == 302
        customer.refresh_from_db()
        assert customer.first_name == "Alicia"
        assert customer.customer_profile.city == "Town"

    def test_vendor_profile_form_cannot_change_approval_or_commission(self, vendor_client, vendor):
        response = vendor_client.post(
            reverse("accounts:vendor_profile"),
            {
                "business_name": "Vera Renamed", "business_description": "", "business_email": "v@example.com",
                "business_phone": "1", "business_address": "a", "business_city": "b", "business_state": "c",
                "business_zip_code": "d", "business_country": "USA", "tax_id": "", "business_registration_number": "",
                "first_name": "", "last_name": "", "email": vendor.user.email, "phone": "",
                "approval_status": "approved", "commission_rate": "0", "store_slug": "hijack",
            },
        )
        assert response.status_code == 302
        vendor.refresh_from_db()
        assert vendor.business_name == "Vera Renamed"
        assert vendor.commission_rate == 10
        assert vendor.store_slug == "vera-goods"

    def test_public_store_hides_unapproved_vendor(self, client, vendor, pending_vendor, product):
        assert client.get(reverse("accounts:vendor_store", args=[vendor.store_slug])).status_code == 200
        assert client.get(reverse("accounts:vendor_store", args=[pending_vendor.store_slug])).status_code == 404


class TestWishlist:
    def test_toggle_requires_post_and_is_idempotent(self, customer_client, customer, product):
        url = reverse("accounts:toggle_wishlist", args=[product.pk])
        assert customer_client.get(url).status_code == 405
        customer_client.post(url)
        customer_client.post(reverse("accounts:toggle_wishlist", args=[product.pk]) + "")
        assert customer.wishlist.products.count() == 0
        customer_client.post(url)
        assert list(customer.wishlist.products.all()) == [product]

    def test_toggle_ignores_external_next(self, customer_client, product):
        response = customer_client.post(
            reverse("accounts:toggle_wishlist", args=[product.pk]), {"next": "https://evil.example/x"}
        )
        assert response.url == product.get_absolute_url()

    def test_move_to_cart(self, customer_client, customer, product):
        customer.wishlist.products.add(product)
        customer_client.post(reverse("accounts:wishlist_move_to_cart", args=[product.pk]))
        assert customer.cart_items.get().product == product
        assert customer.wishlist.products.count() == 0

    def test_wishlist_page_renders(self, customer_client, customer, product):
        customer.wishlist.products.add(product)
        response = customer_client.get(reverse("accounts:wishlist"))
        assert response.status_code == 200
        assert product.name in response.content.decode()
