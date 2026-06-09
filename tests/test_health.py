"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test class for health check endpoints."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Test that GET /health returns 200 status code."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client: TestClient) -> None:
        """Test that GET /health returns status=ok."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_service_name(self, client: TestClient) -> None:
        """Test that GET /health returns service name."""
        response = client.get("/health")
        data = response.json()
        assert data["service"] == "enterprise-ai-agent"

    def test_health_returns_version(self, client: TestClient) -> None:
        """Test that GET /health returns version."""
        response = client.get("/health")
        data = response.json()
        assert data["version"] == "0.1.0"

    def test_health_ready_returns_200(self, client: TestClient) -> None:
        """Test that GET /health/ready returns 200 status code."""
        response = client.get("/health/ready")
        assert response.status_code == 200

    def test_health_ready_returns_ok_status(self, client: TestClient) -> None:
        """Test that GET /health/ready returns status=ok."""
        response = client.get("/health/ready")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_live_returns_200(self, client: TestClient) -> None:
        """Test that GET /health/live returns 200 status code."""
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_health_live_returns_ok_status(self, client: TestClient) -> None:
        """Test that GET /health/live returns status=ok."""
        response = client.get("/health/live")
        data = response.json()
        assert data["status"] == "ok"


class TestAppLoadable:
    """Test that the FastAPI app can be loaded."""

    def test_app_can_be_imported(self) -> None:
        """Test that the app module can be imported."""
        from app.main import app
        assert app is not None

    def test_app_has_correct_title(self) -> None:
        """Test that the app has the correct title."""
        from app.main import app
        assert app.title == "enterprise-ai-agent"

    def test_app_has_correct_version(self) -> None:
        """Test that the app has the correct version."""
        from app.main import app
        assert app.version == "0.1.0"