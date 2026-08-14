"""Sector comparison (#92): stock vs its sector's median, reusing #88's
fit_service.peer_metrics (one bulk read per data source, never a per-symbol
fan-out — the same house rule #88 already set).

Offline — db.query_rows is dispatched by SQL fragment to canned rows.
"""
import pytest

from backend import db, sector_comparison_service as svc

# A thin sector: GP + 2 other Telecom peers (2 < MIN_COHORT=5).
THIN_DM = [
    {"Symbol": "GP", "Sector": "Telecom", "LTP": 300.0},
    {"Symbol": "ROBI", "Sector": "Telecom", "LTP": 30.0},
    {"Symbol": "BATBC", "Sector": "Telecom", "LTP": 500.0},
]
THIN_PRICE = [
    {"Symbol": "GP", "pe": 10.0, "vol": 0.05, "bars": 30},
    {"Symbol": "ROBI", "pe": 20.0, "vol": 0.15, "bars": 30},
    {"Symbol": "BATBC", "pe": 15.0, "vol": 0.08, "bars": 30},
]

# A well-populated sector: GP + 5 other Telecom peers (5 >= MIN_COHORT).
# Peer P/Es (excluding GP): 12, 14, 16, 18, 20 -> median 16.
FULL_DM = [{"Symbol": s, "Sector": "Telecom", "LTP": 100.0}
           for s in ["GP", "A", "B", "C", "D", "E"]]
FULL_PRICE = [
    {"Symbol": "GP", "pe": 10.0, "vol": 0.05, "bars": 30},
    {"Symbol": "A", "pe": 12.0, "vol": 0.05, "bars": 30},
    {"Symbol": "B", "pe": 14.0, "vol": 0.05, "bars": 30},
    {"Symbol": "C", "pe": 16.0, "vol": 0.05, "bars": 30},
    {"Symbol": "D", "pe": 18.0, "vol": 0.05, "bars": 30},
    {"Symbol": "E", "pe": 20.0, "vol": 0.05, "bars": 30},
]


def wire(monkeypatch, dm, price, earn=None, div=None, sector="Telecom"):
    def dispatch(sql, params=None):
        if "SELECT Sector FROM" in sql:
            return [{"Sector": sector}] if sector else []
        if "Symbol, Sector, LTP" in sql:
            return dm
        if "price_archive" in sql:
            return price
        if "fundamentals_earnings" in sql:
            return earn or []
        if "fundamentals_dividends" in sql:
            return div or []
        return []
    monkeypatch.setattr(db, "query_rows", dispatch)


def test_thin_sector_marks_every_metric_not_comparable(monkeypatch):
    wire(monkeypatch, THIN_DM, THIN_PRICE)
    result = svc.compare("gp")

    assert result["symbol"] == "GP"
    assert result["sector"] == "Telecom"
    pe = next(m for m in result["metrics"] if m["metric"] == "pe")
    assert pe["comparable"] is False
    assert pe["sector_median"] is None
    assert pe["peer_count"] == 2                # ROBI + BATBC, GP excluded
    assert pe["subject_value"] == 10.0           # GP's own P/E is still reported


def test_well_populated_sector_computes_the_median_excluding_the_subject(monkeypatch):
    wire(monkeypatch, FULL_DM, FULL_PRICE)
    result = svc.compare("GP")

    pe = next(m for m in result["metrics"] if m["metric"] == "pe")
    assert pe["comparable"] is True
    assert pe["peer_count"] == 5
    assert pe["sector_median"] == 16.0
    assert pe["subject_value"] == 10.0


def test_unknown_sector_returns_an_honest_empty_comparison(monkeypatch):
    wire(monkeypatch, [], [], sector=None)
    result = svc.compare("UNLISTED")

    assert result["sector"] is None
    assert len(result["metrics"]) == 4
    assert all(m["comparable"] is False for m in result["metrics"])
    assert all(m["subject_value"] is None for m in result["metrics"])


def test_response_always_carries_the_four_metrics_with_labels(monkeypatch):
    wire(monkeypatch, THIN_DM, THIN_PRICE)
    result = svc.compare("GP")
    by_key = {m["metric"]: m["label"] for m in result["metrics"]}
    assert by_key == {
        "pe": "P/E",
        "pb": "P/B",
        "yield": "Dividend Yield %",
        "growth": "EPS Growth %/yr",
    }
