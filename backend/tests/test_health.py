import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_health_returns_ok(api_client):
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "kpulla6"
    assert data["database"] == "ok"
