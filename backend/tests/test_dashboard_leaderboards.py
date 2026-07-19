"""Dashboard leaderboards (PRD-12, #82) — endpoint contracts + computed paths.

The endpoint tests patch `market_service` (the route delegates to it) and assert
routing + query validation, not SQL. The service-level tests exercise the
on-read compute path (technical_extremes macd/stochastic) against stubbed rows,
the one place with logic worth testing offline.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend import indicators, market_service
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Endpoint contracts ────────────────────────────────────────────────────────

def test_leaderboard_delegates_and_respects_limit(client):
    fake = [{"Symbol": "ACI", "Sector": "Pharma", "LTP": 250.0, "Value": 5_000_000}]
    with patch("backend.market_service.leaderboard", return_value=fake) as m:
        resp = client.get("/api/market/leaderboard?metric=value&limit=2")
    assert resp.status_code == 200
    assert resp.json() == fake
    m.assert_called_once_with(metric="value", limit=2)


def test_leaderboard_rejects_unknown_metric(client):
    assert client.get("/api/market/leaderboard?metric=bogus").status_code == 422


def test_extremes_delegates(client):
    fake = [{"Symbol": "ACI", "Sector": "Pharma", "LTP": 250.0, "MetricValue": 4.1}]
    with patch("backend.market_service.extremes_leaderboard", return_value=fake) as m:
        resp = client.get("/api/market/extremes?metric=pe_low&limit=2")
    assert resp.status_code == 200
    assert resp.json() == fake
    m.assert_called_once_with(metric="pe_low", limit=2)


def test_extremes_rejects_unknown_metric(client):
    assert client.get("/api/market/extremes?metric=bogus").status_code == 422


def test_technical_extremes_delegates(client):
    fake = [{"Symbol": "ACI", "Sector": "Pharma", "LTP": 250.0, "MetricValue": 22.5}]
    with patch("backend.market_service.technical_extremes", return_value=fake) as m:
        resp = client.get("/api/market/technical-extremes?metric=rsi_low&limit=2")
    assert resp.status_code == 200
    assert resp.json() == fake
    m.assert_called_once_with(metric="rsi_low", limit=2)


def test_technical_extremes_rejects_unknown_metric(client):
    assert client.get("/api/market/technical-extremes?metric=bogus").status_code == 422


def test_market_strength_delegates(client):
    fake = {"Gainers": 180, "Losers": 95, "Unchanged": 25}
    with patch("backend.market_service.market_strength", return_value=fake) as m:
        resp = client.get("/api/market/strength")
    assert resp.status_code == 200
    assert resp.json() == fake
    m.assert_called_once_with()


def test_sector_breakdown_delegates(client):
    fake = [{"Sector": "Pharma", "AvgPE": 12.0, "TotalTradeValue": 9.0,
             "GainersCount": 3, "LosersCount": 1, "AvgChange": 0.4}]
    with patch("backend.market_service.sector_breakdown", return_value=fake) as m:
        resp = client.get("/api/market/sectors/breakdown")
    assert resp.status_code == 200
    assert resp.json() == fake


# ── Service: leaderboard routing ──────────────────────────────────────────────

def test_leaderboard_trade_routes_to_top_trade():
    with patch("backend.market_service.top_trade", return_value=["x"]) as m:
        assert market_service.leaderboard("trade", limit=5) == ["x"]
    m.assert_called_once_with(5)


# ── Service: technical_extremes computed path ─────────────────────────────────

def _bars(symbol, closes, highs=None, lows=None):
    highs = highs or closes
    lows = lows or closes
    return [
        {"Symbol": symbol, "Sector": "S", "LTP": closes[-1],
         "Date": i, "High": highs[i], "Low": lows[i], "Close": closes[i]}
        for i in range(len(closes))
    ]


def test_technical_extremes_rsi_reads_column_not_computed():
    with patch("backend.market_service.db.query_rows", return_value=[{"MetricValue": 20}]) as q:
        market_service.technical_extremes("rsi_low", limit=3)
    # RSI comes straight from the RSI_14_ column — a single read, no groupby.
    sql = q.call_args[0][0]
    assert "RSI_14_" in sql and "ORDER BY RSI_14_ ASC" in sql


def test_technical_extremes_stochastic_ranks_symbols():
    # AAA sits at the top of its range (%K≈100), BBB at the bottom (%K≈0).
    highs = [10.0] * 20
    lows = [0.0] * 20
    aaa = _bars("AAA", closes=[9.5] * 20, highs=highs, lows=lows)
    bbb = _bars("BBB", closes=[0.5] * 20, highs=highs, lows=lows)
    with patch("backend.market_service.db.query_rows", return_value=aaa + bbb):
        high = market_service.technical_extremes("stochastic_high", limit=10)
    assert [r["Symbol"] for r in high] == ["AAA", "BBB"]
    assert high[0]["MetricValue"] == 95.0


def test_technical_extremes_skips_symbols_too_short_to_compute():
    # 5 bars can't yield a MACD (needs >= 26) — the symbol drops out silently.
    short = _bars("AAA", closes=[1.0, 2.0, 3.0, 4.0, 5.0])
    with patch("backend.market_service.db.query_rows", return_value=short):
        assert market_service.technical_extremes("macd_high", limit=10) == []


# ── Unit: stochastic ──────────────────────────────────────────────────────────

def test_stochastic_at_range_top_is_100():
    assert indicators.stochastic([10] * 14, [0] * 14, [10] * 14) == 100.0


def test_stochastic_flat_range_is_neutral_midpoint():
    assert indicators.stochastic([5] * 14, [5] * 14, [5] * 14) == 50.0


def test_stochastic_needs_a_full_period():
    assert indicators.stochastic([10] * 5, [0] * 5, [5] * 5) is None
