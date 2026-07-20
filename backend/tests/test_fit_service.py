"""Fit service (#88): cohort built by bulk reads, wired to the pure engine.

Offline — db.query_rows is dispatched by SQL fragment to canned rows, so the
four bulk cohort queries + the profile read are all faked.
"""
import pytest

from backend import db, fit_service


DM = [
    {"Symbol": "GP", "LTP": 300.0, "Forward_PE": 10.0, "Audited_PE": 12.0},
    {"Symbol": "ROBI", "LTP": 30.0, "Forward_PE": 20.0, "Audited_PE": None},
    {"Symbol": "BATBC", "LTP": 500.0, "Forward_PE": 15.0, "Audited_PE": None},
]
EARN = [
    {"symbol": "GP", "year": 2018, "eps": 5.0, "nav": 40.0},
    {"symbol": "GP", "year": 2024, "eps": 12.0, "nav": 60.0},
    {"symbol": "ROBI", "year": 2018, "eps": 1.0, "nav": 20.0},
    {"symbol": "ROBI", "year": 2024, "eps": 1.5, "nav": 22.0},
    {"symbol": "BATBC", "year": 2018, "eps": 8.0, "nav": 90.0},
    {"symbol": "BATBC", "year": 2024, "eps": 20.0, "nav": 110.0},
]
DIV = [
    {"symbol": "GP", "year": 2024, "dividend_type": "ANNUAL",
     "cash_dividend_pct": 200.0, "publish_date": "2024-06-01"},
    {"symbol": "BATBC", "year": 2024, "dividend_type": "ANNUAL",
     "cash_dividend_pct": 400.0, "publish_date": "2024-06-01"},
]
VOL = [
    {"Symbol": "GP", "vol": 0.05},
    {"Symbol": "ROBI", "vol": 0.15},
    {"Symbol": "BATBC", "vol": 0.08},
]


@pytest.fixture
def wired(monkeypatch):
    def dispatch(sql, params=None):
        if "investor_profiles" in sql:
            return []                              # no profile -> neutral default
        if "SELECT Sector FROM" in sql:
            return [{"Sector": "Telecom"}]
        if "Forward_PE" in sql:
            return DM
        if "fundamentals_earnings" in sql:
            return EARN
        if "fundamentals_dividends" in sql:
            return DIV
        if "price_archive" in sql:
            return VOL
        return []
    monkeypatch.setattr(db, "query_rows", dispatch)


def test_fit_for_scores_the_subject_against_its_cohort(wired):
    res = fit_service.fit_for("u1", "gp")
    assert res["symbol"] == "GP"
    axes = {a["axis"]: a for a in res["axes"]}
    assert set(axes) == {"Value", "Income", "Growth", "Risk", "Sector"}
    # GP is the cheapest (P/E 10) and least volatile of the three -> scores well.
    assert axes["Value"]["score"] is not None
    assert axes["Risk"]["score"] is not None
    assert res["composite"] is not None
    assert res["is_default_profile"] is True       # neutral profile used
    assert res["disclaimer"]


def test_unknown_symbol_returns_all_null_axes_not_a_crash(monkeypatch):
    monkeypatch.setattr(db, "query_rows", lambda sql, params=None:
                        [] if "investor_profiles" in sql or "Sector" in sql else [])
    res = fit_service.fit_for("u1", "NOSUCH")
    assert res["symbol"] == "NOSUCH"
    assert res["composite"] is None                # nothing scored, no crash
