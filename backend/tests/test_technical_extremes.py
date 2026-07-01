from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_technical_extremes_rsi_low_returns_ranked_list_respecting_limit(client):
    fake_rows = [
        {"Symbol": "ACI", "Sector": "Pharma", "LTP": 250.0, "MetricValue": 22.5},
        {"Symbol": "BEXIMCO", "Sector": "Textile", "LTP": 120.0, "MetricValue": 25.1},
    ]
    with patch("backend.bq_service.technical_extremes", return_value=fake_rows) as mock_extremes:
        resp = client.get("/api/market/technical-extremes?metric=rsi_low&limit=2")
    assert resp.status_code == 200
    assert resp.json() == fake_rows
    mock_extremes.assert_called_once_with(metric="rsi_low", limit=2)


def test_technical_extremes_rejects_unknown_metric(client):
    resp = client.get("/api/market/technical-extremes?metric=bogus")
    assert resp.status_code == 422
