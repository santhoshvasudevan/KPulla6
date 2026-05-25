import pytest

from portfolios.constants import DEFAULT_PORTFOLIO_NAME, MAX_ACTIVE_PORTFOLIOS, VIRTUAL_ALL_PORTFOLIOS_NAME
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio


@pytest.mark.django_db
def test_list_returns_active_real_portfolios(api_client, seeded):
    inactive = Portfolio.objects.create(name="Inactive", is_active=False)
    response = api_client.get("/api/v1/portfolios")
    assert response.status_code == 200
    data = response.json()
    ids = {p["id"] for p in data}
    assert inactive.id not in ids
    assert all(p["is_active"] for p in data)


@pytest.mark.django_db
def test_list_does_not_return_virtual_all_portfolios(api_client, seeded):
    response = api_client.get("/api/v1/portfolios")
    names = {p["name"] for p in response.json()}
    assert VIRTUAL_ALL_PORTFOLIOS_NAME not in names


@pytest.mark.django_db
def test_default_portfolio_is_returned(api_client, seeded):
    default = ensure_default_portfolio()
    response = api_client.get("/api/v1/portfolios")
    match = [p for p in response.json() if p["id"] == default.id][0]
    assert match["name"] == DEFAULT_PORTFOLIO_NAME
    assert match["is_default"] is True


@pytest.mark.django_db
def test_post_creates_portfolio(api_client, seeded):
    response = api_client.post(
        "/api/v1/portfolios",
        {"name": "Growth", "description": "Long term"},
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Growth"
    assert data["description"] == "Long term"
    assert data["base_currency"] == "EUR"
    assert data["is_default"] is False
    assert data["is_active"] is True


@pytest.mark.django_db
def test_post_rejects_empty_name(api_client, seeded):
    response = api_client.post("/api/v1/portfolios", {"name": "   "}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_rejects_duplicate_active_name(api_client, seeded):
    api_client.post("/api/v1/portfolios", {"name": "Unique"}, format="json")
    response = api_client.post("/api/v1/portfolios", {"name": "unique"}, format="json")
    assert response.status_code == 400
    assert "Duplicate" in response.json()["detail"]


@pytest.mark.django_db
def test_post_enforces_max_active_portfolios(api_client, seeded):
    for i in range(MAX_ACTIVE_PORTFOLIOS - 1):
        api_client.post("/api/v1/portfolios", {"name": f"P{i}"}, format="json")
    response = api_client.post("/api/v1/portfolios", {"name": "Overflow"}, format="json")
    assert response.status_code == 400
    assert str(MAX_ACTIVE_PORTFOLIOS) in response.json()["detail"]


@pytest.mark.django_db
def test_put_updates_fields(api_client, seeded):
    created = api_client.post(
        "/api/v1/portfolios",
        {"name": "Edit Me"},
        format="json",
    ).json()
    response = api_client.put(
        f"/api/v1/portfolios/{created['id']}",
        {
            "name": "Edited",
            "description": "Desc",
            "base_currency": "USD",
            "is_active": True,
        },
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Edited"
    assert data["description"] == "Desc"
    assert data["base_currency"] == "USD"


@pytest.mark.django_db
def test_put_rejects_duplicate_active_name(api_client, seeded):
    api_client.post("/api/v1/portfolios", {"name": "First"}, format="json")
    second = api_client.post("/api/v1/portfolios", {"name": "Second"}, format="json").json()
    response = api_client.put(
        f"/api/v1/portfolios/{second['id']}",
        {"name": "first"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_delete_soft_deactivates(api_client, seeded):
    created = api_client.post(
        "/api/v1/portfolios",
        {"name": "To Deactivate"},
        format="json",
    ).json()
    response = api_client.delete(f"/api/v1/portfolios/{created['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert Portfolio.objects.filter(pk=created["id"]).exists()


@pytest.mark.django_db
def test_delete_rejects_default_portfolio(api_client, seeded):
    default = ensure_default_portfolio()
    response = api_client.delete(f"/api/v1/portfolios/{default.id}")
    assert response.status_code == 400
    default.refresh_from_db()
    assert default.is_active is True


@pytest.mark.django_db
def test_unknown_portfolio_returns_404(api_client, seeded):
    response = api_client.put(
        "/api/v1/portfolios/999999",
        {"name": "Nope"},
        format="json",
    )
    assert response.status_code == 404

    response2 = api_client.delete("/api/v1/portfolios/999999")
    assert response2.status_code == 404
