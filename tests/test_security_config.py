"""Configuration and cross-cutting security checks."""

from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "config" / "settings.py"


def load_settings(monkeypatch, **env):
    """Evaluate config/settings.py in isolation with the given environment (ignoring .env)."""
    for key in ["DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DJANGO_SECURE_SSL_REDIRECT",
                "DB_ENGINE", "DJANGO_SECURE_COOKIES"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    source = SETTINGS_FILE.read_text(encoding="utf-8").replace('_load_dotenv(BASE_DIR / ".env")', "")
    namespace = {"__file__": str(SETTINGS_FILE)}
    exec(compile(source, str(SETTINGS_FILE), "exec"), namespace)
    return namespace


def test_secret_key_required_when_debug_off(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        load_settings(monkeypatch, DJANGO_DEBUG="False")


def test_debug_defaults_to_off(monkeypatch):
    assert load_settings(monkeypatch, DJANGO_SECRET_KEY="k" * 50)["DEBUG"] is False


def test_production_security_flags_and_postgres(monkeypatch):
    conf = load_settings(
        monkeypatch,
        DJANGO_DEBUG="False",
        DJANGO_SECRET_KEY="x" * 60,
        DJANGO_ALLOWED_HOSTS="shop.example.com",
        DB_ENGINE="postgresql",
        DB_NAME="corecart",
    )
    assert conf["SESSION_COOKIE_SECURE"] and conf["CSRF_COOKIE_SECURE"]
    assert conf["SECURE_SSL_REDIRECT"] and conf["SECURE_HSTS_SECONDS"] > 0
    assert conf["ALLOWED_HOSTS"] == ["shop.example.com"]
    assert conf["DATABASES"]["default"]["ENGINE"] == "django.db.backends.postgresql"
    assert conf["X_FRAME_OPTIONS"] == "DENY"


def test_unknown_database_engine_rejected(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        load_settings(monkeypatch, DJANGO_SECRET_KEY="k" * 50, DB_ENGINE="oracle")


@pytest.mark.django_db
def test_csrf_enforced_on_state_changing_views(customer, product):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    client.force_login(customer)
    assert client.post(reverse("cart:add", args=[product.pk]), {"quantity": 1}).status_code == 403


@pytest.mark.django_db
def test_clickjacking_and_nosniff_headers(client):
    response = client.get(reverse("core:home"))
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"


def test_tests_run_with_debug_off(settings):
    assert settings.DEBUG is False
