import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_read_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "single-user-local"
    assert "version" in data


def test_health_check():
    """Test health check returns detailed status"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["cache"] == "ok"
    assert "version" in data


def test_openapi_schema():
    """Test OpenAPI schema loads with tags and description"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "Virtual Lab" in schema["info"]["description"]
    tag_names = [t["name"] for t in schema["tags"]]
    assert "teams" in tag_names
    assert "agents" in tag_names
    assert "meetings" in tag_names
    assert "search" in tag_names
    assert "templates" in tag_names
