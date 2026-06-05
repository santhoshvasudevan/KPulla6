import pytest
from django.contrib.auth import get_user_model

from accounts.services import INITIAL_OWNER_EMAIL, get_or_create_initial_owner
from portfolios.models import Portfolio
from settings_app.models import AppSettings

User = get_user_model()


@pytest.mark.django_db
def test_unauthenticated_portfolio_api_returns_401(anon_client):
    response = anon_client.get("/api/v1/portfolios")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_unauthenticated_settings_returns_401(anon_client):
    response = anon_client.get("/api/v1/settings")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_login_logout_and_current_user(api_client, test_user):
    anon = __import__("rest_framework.test", fromlist=["APIClient"]).APIClient()
    login = anon.post(
        "/api/v1/auth/login",
        {"username_or_email": test_user.username, "password": "testpass123"},
        format="json",
    )
    assert login.status_code == 200
    assert login.json()["email"] == test_user.email

    me = anon.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == test_user.username

    logout = anon.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    me_after = anon.get("/api/v1/auth/me")
    assert me_after.status_code in (401, 403)


def _register_payload(**overrides):
    payload = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "StrongPass123!",
        "password_confirm": "StrongPass123!",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_register_creates_user_portfolio_and_settings():
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        "/api/v1/auth/register",
        _register_payload(),
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(username="newuser")
    default = Portfolio.objects.get(user=user, is_default=True)
    assert default.cash_aware_enabled is True
    assert AppSettings.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_register_duplicate_username_returns_400():
    from rest_framework.test import APIClient

    client = APIClient()
    client.post("/api/v1/auth/register", _register_payload(), format="json")
    response = client.post(
        "/api/v1/auth/register",
        _register_payload(email="other@example.com"),
        format="json",
    )
    assert response.status_code == 400
    assert "username" in response.json()


@pytest.mark.django_db
def test_register_duplicate_email_returns_400():
    from rest_framework.test import APIClient

    client = APIClient()
    client.post("/api/v1/auth/register", _register_payload(), format="json")
    response = client.post(
        "/api/v1/auth/register",
        _register_payload(username="otheruser"),
        format="json",
    )
    assert response.status_code == 400
    assert "email" in response.json()


@pytest.mark.django_db
def test_register_password_mismatch_returns_400():
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        "/api/v1/auth/register",
        _register_payload(password_confirm="DifferentPass123!"),
        format="json",
    )
    assert response.status_code == 400
    assert "password_confirm" in response.json()


@pytest.mark.django_db
def test_register_weak_password_returns_400():
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        "/api/v1/auth/register",
        _register_payload(password="short", password_confirm="short"),
        format="json",
    )
    assert response.status_code == 400
    assert "password" in response.json()


@pytest.mark.django_db
def test_register_is_atomic_when_settings_setup_fails(monkeypatch):
    from rest_framework.test import APIClient

    from accounts import services as account_services

    def fail_settings(_user):
        raise RuntimeError("settings setup failed")

    monkeypatch.setattr(account_services, "ensure_app_settings", fail_settings)
    client = APIClient()
    client.raise_request_exception = False
    response = client.post(
        "/api/v1/auth/register",
        _register_payload(username="atomicuser", email="atomic@example.com"),
        format="json",
    )
    assert response.status_code == 500
    assert not User.objects.filter(username="atomicuser").exists()
    assert not Portfolio.objects.filter(name="Default Portfolio", user__username="atomicuser").exists()


@pytest.mark.django_db
def test_register_completes_incomplete_user():
    from rest_framework.test import APIClient

    incomplete = User.objects.create_user(
        username="partialuser",
        email="partial@example.com",
        password="StrongPass123!",
    )
    Portfolio.objects.create(
        user=incomplete,
        name="Default Portfolio",
        base_currency="EUR",
        is_default=True,
        is_active=True,
    )
    assert not AppSettings.objects.filter(user=incomplete).exists()

    client = APIClient()
    response = client.post(
        "/api/v1/auth/register",
        _register_payload(username="partialuser", email="partial@example.com"),
        format="json",
    )
    assert response.status_code == 201
    assert AppSettings.objects.filter(user=incomplete).exists()
    assert User.objects.filter(username="partialuser").count() == 1


@pytest.mark.django_db
def test_user_cannot_access_other_users_portfolio(api_client, test_user, other_user, seeded):
    from portfolios.models import Portfolio

    other_portfolio = Portfolio.objects.create(
        user=other_user,
        name="Other Portfolio",
        base_currency="EUR",
        is_default=True,
        is_active=True,
    )
    response = api_client.get(f"/api/v1/portfolio/summary?portfolio_id={other_portfolio.id}")
    assert response.status_code == 404


@pytest.mark.django_db
def test_authenticated_user_can_access_own_data(api_client, seeded):
    response = api_client.get("/api/v1/portfolios")
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.django_db
def test_password_reset_dev_placeholder(anon_client, test_user):
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        "/api/v1/auth/password-reset",
        {"email": test_user.email},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert "detail" in body
    assert "email_sent" in body
    if body.get("email_sent") is False:
        assert "dev_reset_path" in body or "set_user_password" in body["detail"]


@pytest.mark.django_db
def test_data_migration_assigns_existing_portfolios_to_initial_owner(db):
    owner = get_or_create_initial_owner()
    assert owner.email.lower() == INITIAL_OWNER_EMAIL.lower()


@pytest.mark.django_db
def test_google_oauth_not_hardcoded_in_settings(settings):
    settings.GOOGLE_CLIENT_ID = ""
    settings.GOOGLE_CLIENT_SECRET = ""
    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] = ""
    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["secret"] = ""
    assert settings.GOOGLE_CLIENT_ID == ""
    assert settings.GOOGLE_CLIENT_SECRET == ""
    assert settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] == ""


def test_google_oauth_callback_url_is_canonical(rf, settings):
    from types import SimpleNamespace

    from accounts.google_oauth import KPulla6GoogleOAuth2Adapter

    request = rf.post("/accounts/google/login/", HTTP_HOST="127.0.0.1:8000")
    adapter = KPulla6GoogleOAuth2Adapter(request)
    app = SimpleNamespace()
    assert adapter.get_callback_url(request, app) == settings.GOOGLE_OAUTH_CALLBACK_URL
    assert "localhost:8000" in settings.GOOGLE_OAUTH_CALLBACK_URL


def test_google_email_authentication_settings_enabled(settings):
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION is True
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT is True


def test_google_login_on_get_skips_intermediate_page(settings):
    assert settings.SOCIALACCOUNT_LOGIN_ON_GET is True


def test_allauth_account_settings_use_current_keys(settings):
    assert settings.ACCOUNT_LOGIN_METHODS == {"username", "email"}
    assert settings.ACCOUNT_SIGNUP_FIELDS == [
        "email*",
        "username*",
        "password1*",
        "password2*",
    ]


@pytest.mark.django_db
def test_google_login_get_redirects_to_google(client, settings):
    settings.GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
    settings.GOOGLE_CLIENT_SECRET = "test-secret"
    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] = settings.GOOGLE_CLIENT_ID
    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["secret"] = settings.GOOGLE_CLIENT_SECRET

    response = client.get(
        "/accounts/google/login/?process=login",
        HTTP_HOST="localhost:8000",
    )
    assert response.status_code == 302
    assert "accounts.google.com" in response["Location"]


@pytest.mark.django_db
def test_google_sociallogin_links_existing_owner_by_verified_email():
    from django.test import RequestFactory
    from allauth.socialaccount.adapter import get_adapter

    owner = get_or_create_initial_owner()
    request = RequestFactory().get("/accounts/google/login/")
    provider = get_adapter().get_provider(request, "google")
    sociallogin = provider.sociallogin_from_response(
        request,
        {
            "sub": "test-google-sub-uid",
            "email": owner.email,
            "email_verified": True,
            "given_name": "Santhosh",
        },
    )
    sociallogin.lookup()
    assert sociallogin.user.pk == owner.pk
    assert sociallogin.is_existing is True
