from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_sector_breakdown_returns_per_sector_aggregates(client):
    fake_rows = [
        {"Sector": "Pharma", "AvgPE": 14.2, "TotalTradeValue": 5_000_000, "GainersCount": 12, "LosersCount": 3, "AvgChange": 1.1},
        {"Sector": "Textile", "AvgPE": 9.8, "TotalTradeValue": 2_000_000, "GainersCount": 4, "LosersCount": 9, "AvgChange": -0.6},
    ]
    with patch("backend.bq_service.sector_breakdown", return_value=fake_rows) as mock_breakdown:
        resp = client.get("/api/market/sectors/breakdown")
    assert resp.status_code == 200
    assert resp.json() == fake_rows
    mock_breakdown.assert_called_once_with()
