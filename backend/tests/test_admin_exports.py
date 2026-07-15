"""Tests for the Admin export endpoints."""

import json
import pytest
from fastapi.testclient import TestClient
from backend.api import app
from unittest.mock import patch

def client_with_admin_token(client):
    """
    Simple helper to simulate admin authentication.
    """
    # We'll patch get_current_user or require_admin elsewhere
    return client


@pytest.fixture
def admin_user(client):
    """Create an admin user and return token."""
    resp = client.post(
        "/api/auth/signup",
        json={
            "email": "admin@dscquant.com",
            "password": "admin123",
            "full_name": "Admin User",
            "role": "admin",
            "phone": "1234567890",
        },
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"token": token, "role": "admin"}


@patch("backend.api.require_admin")
def test_admin_export_announcements(mock_require_admin, client, admin_user):
    """Test /api/admin/export/announcements returns CSV with proper headers."""
    # Mock role decorator to bypass the dependency for the test
    mock_require_admin.return_value = {"id": "123", "email": "admin@dscquant.com", "role": "admin"}  # Mock admin user

    resp = client.get("/api/admin/export/announcements")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.headers["content-disposition"].startswith("attachment; filename=")

    csv_content = resp.content.decode("utf-8")
    assert "Symbol" in csv_content
    assert "Date" in csv_content


@patch("backend.api.require_admin")
def test_admin_export_price_archive(mock_require_admin, client, admin_user):
    """Test /api/admin/export/price_archive returns CSV with price data."""
    mock_require_admin.return_value = {"id": "123", "email": "admin@dscquant.com", "role": "admin"}

    resp = client.get("/api/admin/export/price_archive")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.headers["content-disposition"].startswith("attachment; filename=")

    csv_content = resp.content.decode("utf-8")
    assert "Date" in csv_content
    assert "Symbol" in csv_content


@patch("backend.api.require_admin")
def test_admin_export_data_grid(mock_require_admin, client, admin_user):
    """Test /api/admin/export/data_grid returns JSON with dataset info."""
    mock_required = mock_require_admin.return_value = {"id": "123", "email": "admin@dscquant.com", "role": "admin"}

    resp = client.get("/api/admin/export/data_grid")
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("content-type", "")

    data = resp.json()
    assert isinstance(data, dict)
    # Basic check that content looks like JSON export
    assert len(str(data)) > 10
    # Ensure proper formatting (no stray double quotes etc)
    assert '"symbol"' in str(data).lower() or any("symbol" in k.lower() for k in data.keys())

# Ensure non-admin gets blocked
def test_admin_requires_admin_role(client):
    """Ensure non-admin cannot access export."""
    resp = client.get("/api/admin/export/announcements")
    assert resp.status_code == 401