"""Offline tests for the /api/market/screener routes (#71).

Monkeypatches the names api.py bound into its own namespace — see
test_session_endpoints.py's module docstring for why that, not the source
module, is what a route actually calls.
"""
from backend import api, auth, screener_service
from backend.models import UserResponse


def _user(uid="user-1"):
    return UserResponse(id=uid, email="a@x.com", phone="", full_name="", role="user", created_at=None)


_RESULT = [{"symbol": "GP", "sector": "Telecom", "price": 300.0, "volume": 1000,
            "market_cap": 500.0, "pe": 12.0, "pb": 2.0, "dividend_yield": 5.0}]


def test_screener_returns_results(client, monkeypatch):
    monkeypatch.setattr(api.screener_service, "screen", lambda **kw: _RESULT)
    resp = client.post("/api/market/screener", json={"filters": [{"field": "pe", "op": "lte", "value": 15}]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 1
    assert data["results"][0]["symbol"] == "GP"


def test_screener_passes_preset_and_filters_through(client, monkeypatch):
    captured = {}

    def fake_screen(**kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(api.screener_service, "screen", fake_screen)
    client.post("/api/market/screener", json={
        "preset": "value", "filters": [{"field": "sector", "op": "eq", "value": "Banks"}], "limit": 50,
    })
    assert captured["preset"] == "value"
    assert captured["filters"] == [{"field": "sector", "op": "eq", "value": "Banks"}]
    assert captured["limit"] == 50


def test_screener_unknown_field_is_400(client):
    # No monkeypatch: exercises the real screener_service.screen -> InvalidFilter -> 400.
    resp = client.post("/api/market/screener", json={"filters": [{"field": "rsi", "op": "gt", "value": 70}]})
    assert resp.status_code == 400


def test_screener_unknown_preset_is_400(client):
    resp = client.post("/api/market/screener", json={"preset": "momentum"})
    assert resp.status_code == 400


def test_screener_export_returns_csv(client, monkeypatch):
    monkeypatch.setattr(api.screener_service, "screen", lambda **kw: _RESULT)
    resp = client.post("/api/market/screener/export", json={})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert resp.headers["content-disposition"] == "attachment; filename=screener_results.csv"
    assert "GP" in resp.content.decode("utf-8")


def test_screener_export_unknown_field_is_400(client):
    resp = client.post("/api/market/screener/export", json={"filters": [{"field": "rsi", "op": "gt", "value": 70}]})
    assert resp.status_code == 400


def test_screener_watchlist_requires_auth(client):
    resp = client.post("/api/market/screener/watchlist", json={"symbols": ["GP"]})
    assert resp.status_code == 401


def test_screener_watchlist_adds_each_symbol(client, monkeypatch):
    calls = []
    monkeypatch.setattr(api.watchlist_service, "add_to_watchlist",
                        lambda uid, symbol: calls.append((uid, symbol)) or {"id": "x", "symbol": symbol})
    api.app.dependency_overrides[auth.get_current_user] = lambda: _user(uid="user-7")
    try:
        resp = client.post("/api/market/screener/watchlist", json={"symbols": ["GP", "BEXIMCO"]})
    finally:
        api.app.dependency_overrides.pop(auth.get_current_user, None)

    assert resp.status_code == 200, resp.text
    assert calls == [("user-7", "GP"), ("user-7", "BEXIMCO")]
    assert len(resp.json()["added"]) == 2
