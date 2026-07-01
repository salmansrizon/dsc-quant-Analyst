from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_market_strength_returns_gainer_loser_unchanged_composition(client):
    fake_composition = {"Gainers": 180, "Losers": 95, "Unchanged": 25}
    with patch("backend.bq_service.market_strength", return_value=fake_composition) as mock_strength:
        resp = client.get("/api/market/strength")
    assert resp.status_code == 200
    assert resp.json() == fake_composition
    mock_strength.assert_called_once_with()
