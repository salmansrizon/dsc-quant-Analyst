from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_extremes_pe_low_returns_ranked_list_respecting_limit(client):
    fake_rows = [
        {"Symbol": "ACI", "Sector": "Pharma", "LTP": 250.0, "MetricValue": 4.1},
        {"Symbol": "BEXIMCO", "Sector": "Textile", "LTP": 120.0, "MetricValue": 5.6},
    ]
    with patch("backend.bq_service.extremes_leaderboard", return_value=fake_rows) as mock_extremes:
        resp = client.get("/api/market/extremes?metric=pe_low&limit=2")
    assert resp.status_code == 200
    assert resp.json() == fake_rows
    mock_extremes.assert_called_once_with(metric="pe_low", limit=2)


def test_extremes_rejects_unknown_metric(client):
    resp = client.get("/api/market/extremes?metric=bogus")
    assert resp.status_code == 422
