"""Rendering, navigation and template integrity checks."""

from pathlib import Path

import pytest
from django.conf import settings
from django.template import engines
from django.template.loader import get_template
from django.urls import reverse

from orders import services
from support.services import open_ticket

pytestmark = pytest.mark.django_db

TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates"


def all_templates():
    return sorted(str(p.relative_to(TEMPLATE_DIR)).replace("\\", "/") for p in TEMPLATE_DIR.rglob("*.*"))


@pytest.mark.parametrize("name", all_templates())
def test_every_template_compiles(name):
    get_template(name)


def test_no_css_framework_or_cdn():
    css = (Path(settings.BASE_DIR) / "static/css/main.css").read_text(encoding="utf-8")
    base = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")
    for marker in ("bootstrap", "tailwind", "bulma", "jquery", "cdn."):
        assert marker not in css.lower() and marker not in base.lower()


def test_public_pages(client, product, vendor):
    for url in [reverse("core:home"), reverse("core:about"), reverse("products:list"), product.get_absolute_url(),
                reverse("accounts:login"), reverse("accounts:register"), reverse("accounts:customer_register"),
                reverse("accounts:vendor_register"), reverse("accounts:password_reset"),
                reverse("accounts:vendor_store", args=[vendor.store_slug])]:
        response = client.get(url)
        assert response.status_code == 200, url
        html = response.content.decode()
        assert '<main id="main"' in html and 'name="viewport"' in html


def test_home_empty_state(client):
    assert "The shelves are being stocked" in client.get(reverse("core:home")).content.decode()


def test_customer_pages(customer_client, customer, product, fill_cart, shipping):
    fill_cart(customer, product)
    order, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="f")
    ticket = open_ticket(customer, "Question", "A question about the product please")
    fill_cart(customer, product)
    for url in [reverse("accounts:customer_dashboard"), reverse("accounts:customer_profile"),
                reverse("accounts:wishlist"), reverse("cart:view"), reverse("orders:checkout"),
                reverse("orders:list"), order.get_absolute_url(), reverse("orders:invoice", args=[order.order_number]),
                reverse("support:ticket_list"), reverse("support:ticket_create"), ticket.get_absolute_url(),
                reverse("accounts:password_change")]:
        assert customer_client.get(url).status_code == 200, url


def test_vendor_pages(vendor_client, product, customer, fill_cart, shipping):
    fill_cart(customer, product)
    order, _ = services.place_order(customer, shipping=shipping, payment_method="cod", checkout_token="g")
    for url in [reverse("accounts:vendor_dashboard"), reverse("accounts:vendor_profile"),
                reverse("products:vendor_list"), reverse("products:create"),
                reverse("products:update", args=[product.pk]), reverse("products:delete", args=[product.pk]),
                reverse("products:inventory"), reverse("products:vendor_reviews"), reverse("products:vendor_questions"),
                reverse("orders:vendor_order_list"), reverse("orders:vendor_order_detail", args=[order.order_number]),
                reverse("analytics:vendor_dashboard")]:
        assert vendor_client.get(url).status_code == 200, url


def test_admin_pages(admin_client_):
    for url in [reverse("analytics:admin_dashboard"), reverse("support:staff_ticket_list"), reverse("admin:index")]:
        assert admin_client_.get(url).status_code == 200, url


def test_navigation_links_by_role(customer, vendor, admin_user):
    from django.test import Client

    def home_as(user=None):
        client = Client()
        if user is not None:
            client.force_login(user)
        return client.get(reverse("core:home")).content.decode()

    anon = home_as()
    assert reverse("accounts:login") in anon and reverse("cart:view") in anon
    cust = home_as(customer)
    assert reverse("orders:list") in cust and reverse("accounts:logout") in cust
    assert reverse("products:vendor_list") not in cust
    vend = home_as(vendor.user)
    assert reverse("products:vendor_list") in vend and f'href="{reverse("cart:view")}"' not in vend
    adm = home_as(admin_user)
    assert reverse("analytics:admin_dashboard") in adm


def test_form_errors_are_rendered_accessibly(client):
    html = client.post(reverse("accounts:customer_register"), {"username": ""}).content.decode()
    assert 'class="field__errors"' in html and 'aria-invalid="true"' in html
    assert 'role="alert"' in html


def test_logout_is_a_post_form(customer_client):
    html = customer_client.get(reverse("core:home")).content.decode()
    assert f'<form method="post" action="{reverse("accounts:logout")}">' in html


def test_custom_404_page(client):
    response = client.get("/products/does-not-exist/")
    assert response.status_code == 404
    assert "find that page" in response.content.decode()


def test_user_content_is_escaped(client, make_product):
    product = make_product(name="<script>alert(1)</script>")
    html = client.get(product.get_absolute_url()).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_chart_labels_escaped():
    template = engines["django"].from_string("{% load chart_tags %}{% bar_chart data 'T' %}")
    html = template.render({"data": [{"label": "<img src=x onerror=alert(1)>", "value": 5}]})
    assert "<img src=x" not in html and "&lt;img" in html


def test_responsive_meta_and_reduced_motion():
    css = (Path(settings.BASE_DIR) / "static/css/main.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css and "@media (min-width" in css
