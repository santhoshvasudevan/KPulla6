import pytest

from settings_app.models import AppSettings


@pytest.mark.django_db
def test_get_settings_returns_defaults_when_seeded(api_client, seeded):
    response = api_client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert data == {"tax_rate_percentage": 0.0, "display_currency": "EUR"}
    assert AppSettings.objects.count() == 1


@pytest.mark.django_db
def test_put_updates_tax_rate_percentage(api_client, seeded):
    response = api_client.put(
        "/api/v1/settings",
        {"tax_rate_percentage": 20.0},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["tax_rate_percentage"] == 20.0
    assert response.json()["display_currency"] == "EUR"


@pytest.mark.django_db
def test_put_updates_display_currency(api_client, seeded):
    response = api_client.put(
        "/api/v1/settings",
        {"display_currency": "USD"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json() == {"tax_rate_percentage": 0.0, "display_currency": "USD"}


@pytest.mark.django_db
def test_put_rejects_unsupported_display_currency(api_client, seeded):
    response = api_client.put(
        "/api/v1/settings",
        {"display_currency": "ZZZ"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_put_rejects_invalid_tax_rate_percentage(api_client, seeded):
    response = api_client.put(
        "/api/v1/settings",
        {"tax_rate_percentage": -1},
        format="json",
    )
    assert response.status_code == 400

    response2 = api_client.put(
        "/api/v1/settings",
        {"tax_rate_percentage": 101},
        format="json",
    )
    assert response2.status_code == 400


@pytest.mark.django_db
def test_settings_singleton(api_client, seeded):
    api_client.put("/api/v1/settings", {"tax_rate_percentage": 15.0}, format="json")
    api_client.put("/api/v1/settings", {"display_currency": "INR"}, format="json")
    assert AppSettings.objects.count() == 1
    settings = AppSettings.objects.get(pk=1)
    assert float(settings.tax_rate_percentage) == 15.0
    assert settings.display_currency == "INR"
