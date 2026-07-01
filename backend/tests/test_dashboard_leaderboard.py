from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_leaderboard_value_returns_ranked_list_respecting_limit(client):
    fake_rows = [
        {"Symbol": "ACI", "Sector": "Pharma", "LTP": 250.0, "ChangePct": 1.2, "Value": 5_000_000},
        {"Symbol": "BEXIMCO", "Sector": "Textile", "LTP": 120.0, "ChangePct": -0.5, "Value": 3_000_000},
    ]
    with patch("backend.bq_service.leaderboard", return_value=fake_rows) as mock_leaderboard:
        resp = client.get("/api/market/leaderboard?metric=value&limit=2")
    assert resp.status_code == 200
    assert resp.json() == fake_rows
    mock_leaderboard.assert_called_once_with(metric="value", limit=2)


def test_leaderboard_rejects_unknown_metric(client):
    resp = client.get("/api/market/leaderboard?metric=bogus")
    assert resp.status_code == 422
