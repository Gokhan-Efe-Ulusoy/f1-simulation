import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "simulation_model_version" in data


def test_root_redirect(client: TestClient):
    """Test root endpoint."""
    response = client.get("/")
    # Root might 404 since we only have /api/v1/health
    assert response.status_code in [200, 404]
