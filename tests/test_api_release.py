"""Release hardening for browser (SPA) clients: refresh cookie, CORS, caching, JSON errors, config."""

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from .conftest import PASSWORD
from .test_security_config import load_settings

pytestmark = pytest.mark.django_db

XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def cookie_login(client):
    return client.post(reverse("api:token"), {"username": "alice", "password": PASSWORD, "use_cookie": True},
                       format="json")


class TestRefreshCookie:
    def test_login_sets_httponly_cookie_and_hides_refresh(self, customer, settings):
        client = APIClient()
        response = cookie_login(client)
        assert response.status_code == 200
        body = response.json()
        assert "refresh" not in body and body["access"]
        cookie = response.cookies[settings.JWT_REFRESH_COOKIE_NAME]
        assert cookie["httponly"] and cookie["path"] == "/api/v1/auth/" and cookie["samesite"] == "Lax"
        assert cookie["secure"]  # DEBUG is off in tests

    def test_refresh_via_cookie_rotates_cookie(self, customer, settings):
        client = APIClient()
        old = cookie_login(client).cookies[settings.JWT_REFRESH_COOKIE_NAME].value
        response = client.post(reverse("api:token-refresh"), {}, format="json", **XHR)
        assert response.status_code == 200 and response.json()["access"] and "refresh" not in response.json()
        new = response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value
        assert new and new != old
        # The rotated-out token is blacklisted.
        client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = old
        assert client.post(reverse("api:token-refresh"), {}, format="json", **XHR).status_code == 401

    def test_cookie_refresh_requires_custom_header(self, customer):
        client = APIClient()
        cookie_login(client)
        assert client.post(reverse("api:token-refresh"), {}, format="json").status_code == 403

    def test_logout_blacklists_and_clears_cookie(self, customer, settings):
        client = APIClient()
        token = cookie_login(client).cookies[settings.JWT_REFRESH_COOKIE_NAME].value
        response = client.post(reverse("api:logout"), {}, format="json", **XHR)
        assert response.status_code == 205
        assert response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value == ""
        client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = token
        assert client.post(reverse("api:token-refresh"), {}, format="json", **XHR).status_code == 401

    def test_body_mode_unchanged_for_mobile_clients(self, customer):
        response = APIClient().post(reverse("api:token"), {"username": "alice", "password": PASSWORD}, format="json")
        assert "refresh" in response.json() and not response.cookies

    def test_register_with_cookie(self, settings):
        response = APIClient().post(
            reverse("api:register-customer"),
            {"username": "spa", "first_name": "S", "last_name": "P", "email": "spa@example.com",
             "password": "Vivid-Orchard-42", "use_cookie": True},
            format="json",
        )
        assert response.status_code == 201 and "refresh" not in response.json()
        assert response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value

    def test_missing_token_is_400(self):
        assert APIClient().post(reverse("api:logout"), {}, format="json").status_code == 400


class TestCors:
    ORIGIN = "http://localhost:5173"

    def test_allowed_origin_gets_credentials_headers(self, settings, product):
        settings.CORS_ALLOWED_ORIGINS = [self.ORIGIN]
        response = APIClient().get(reverse("api:product-list"), HTTP_ORIGIN=self.ORIGIN)
        assert response["Access-Control-Allow-Origin"] == self.ORIGIN
        assert response["Access-Control-Allow-Credentials"] == "true"

    def test_preflight_allows_idempotency_key(self, settings):
        settings.CORS_ALLOWED_ORIGINS = [self.ORIGIN]
        response = APIClient().options(
            reverse("api:checkout"), HTTP_ORIGIN=self.ORIGIN, HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,idempotency-key,content-type",
        )
        assert "idempotency-key" in response["Access-Control-Allow-Headers"]

    def test_unknown_origin_not_allowed(self, settings, product):
        settings.CORS_ALLOWED_ORIGINS = [self.ORIGIN]
        response = APIClient().get(reverse("api:product-list"), HTTP_ORIGIN="https://evil.example")
        assert "Access-Control-Allow-Origin" not in response

    def test_cors_limited_to_api(self, settings, client):
        settings.CORS_ALLOWED_ORIGINS = [self.ORIGIN]
        assert "Access-Control-Allow-Origin" not in client.get(reverse("core:home"), HTTP_ORIGIN=self.ORIGIN)


class TestCachingAndErrors:
    def test_public_catalogue_is_cacheable_with_etag(self, api, product):
        response = api().get(reverse("api:product-list"))
        assert "public" in response["Cache-Control"] and "max-age=60" in response["Cache-Control"]
        assert "Authorization" in response["Vary"]
        etag = response["ETag"]
        assert api().get(reverse("api:product-list"), HTTP_IF_NONE_MATCH=etag).status_code == 304

    def test_authenticated_responses_are_private(self, api, customer, product):
        response = api(customer).get(reverse("api:product-list"))
        assert "private" in response["Cache-Control"]

    def test_unknown_api_url_returns_json_404(self, client):
        response = client.get("/api/v1/does-not-exist/")
        assert response.status_code == 404 and response.json() == {"detail": "Not found.", "code": "not_found"}

    def test_category_product_counts(self, api, make_product, pending_vendor):
        make_product()
        make_product(name="Hidden", owner=pending_vendor)
        assert api().get(reverse("api:category-list")).json()[0]["product_count"] == 1


class TestProductionConfig:
    BASE = {"DJANGO_DEBUG": "False", "DJANGO_SECRET_KEY": "k" * 60, "DJANGO_ALLOWED_HOSTS": "api.example.com"}

    def test_redis_cache(self, monkeypatch):
        conf = load_settings(monkeypatch, REDIS_URL="redis://cache:6379/0", **self.BASE)
        assert conf["CACHES"]["default"]["BACKEND"] == "django.core.cache.backends.redis.RedisCache"

    def test_s3_media_storage(self, monkeypatch):
        conf = load_settings(monkeypatch, MEDIA_STORAGE="s3", S3_BUCKET_NAME="media-bucket",
                             S3_CUSTOM_DOMAIN="cdn.example.com", **self.BASE)
        default = conf["STORAGES"]["default"]
        assert default["BACKEND"] == "storages.backends.s3.S3Storage"
        assert default["OPTIONS"]["bucket_name"] == "media-bucket"
        assert conf["STORAGES"]["staticfiles"]["BACKEND"].endswith("ManifestStaticFilesStorage")

    def test_s3_requires_bucket(self, monkeypatch):
        from django.core.exceptions import ImproperlyConfigured

        with pytest.raises(ImproperlyConfigured):
            load_settings(monkeypatch, MEDIA_STORAGE="s3", **self.BASE)

    def test_spa_origin_trusted_for_csrf(self, monkeypatch):
        conf = load_settings(monkeypatch, CORS_ALLOWED_ORIGINS="https://app.example.com", **self.BASE)
        assert conf["CORS_ALLOWED_ORIGINS"] == ["https://app.example.com"]
        assert "https://app.example.com" in conf["CSRF_TRUSTED_ORIGINS"]
        assert conf["JWT_REFRESH_COOKIE_SECURE"] is True

    def test_deploy_checks_flag_locmem_cache(self, settings):
        from core.checks import corecart_deploy_checks

        settings.CORS_ALLOWED_ORIGINS = []
        ids = {issue.id for issue in corecart_deploy_checks(None)}
        assert {"corecart.W001", "corecart.W002", "corecart.W004"} <= ids
        settings.JWT_REFRESH_COOKIE_SAMESITE = "None"
        settings.JWT_REFRESH_COOKIE_SECURE = False
        assert "corecart.E001" in {issue.id for issue in corecart_deploy_checks(None)}


def test_openapi_schema_is_valid(tmp_path):
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(tmp_path / "schema.yml"))
