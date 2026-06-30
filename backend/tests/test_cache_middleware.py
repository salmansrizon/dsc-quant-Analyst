from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Behavior 1: public GET gets Cache-Control header ─────────────────────────

def test_public_get_returns_cache_control_header(client):
    with patch("backend.bq_service.market_summary", return_value={"total": 1}):
        resp = client.get("/api/market/summary")
    assert "cache-control" in resp.headers
    assert "public" in resp.headers["cache-control"]
    assert "max-age=300" in resp.headers["cache-control"]


# ── Behavior 2: authenticated GET does NOT get cache header ───────────────────

def test_authenticated_get_has_no_public_cache_header(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer fake-token"})
    cache = resp.headers.get("cache-control", "")
    assert "public" not in cache


# ── Behavior 3: POST is never cached ─────────────────────────────────────────

def test_post_has_no_cache_control_header(client):
    resp = client.post("/api/auth/login", json={"email": "x@x.com", "password": "wrong"})
    cache = resp.headers.get("cache-control", "")
    assert "public" not in cache


# ── Behavior 4: /api/market/summary returns valid summary data ────────────────

def test_market_summary_returns_valid_data(client):
    fake_summary = {
        "total_stocks": 414,
        "total_sectors": 24,
        "avg_price": 45.2,
        "total_turnover": 12000000,
        "last_updated": "2026-06-29",
    }
    with patch("backend.bq_service.market_summary", return_value=fake_summary):
        resp = client.get("/api/market/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_stocks" in data
    assert data["total_stocks"] == 414


# ── Behavior 5: /api/market/sectors returns a non-empty list ─────────────────

def test_market_sectors_returns_list(client):
    fake_sectors = [
        {"sector": "Bank", "stock_count": 30, "avg_ltp": 22.5},
        {"sector": "Cement", "stock_count": 12, "avg_ltp": 55.0},
    ]
    with patch("backend.bq_service.list_sectors", return_value=fake_sectors):
        resp = client.get("/api/market/sectors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "sector" in data[0]
