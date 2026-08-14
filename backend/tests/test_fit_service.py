"""Fit service (#88): cohort built by bulk reads, wired to the pure engine.

Offline — db.query_rows is dispatched by SQL fragment to canned rows, so the
four bulk cohort queries + the profile read are all faked.
"""
import pytest

from backend import db, fit_service

# conftest.py's autouse clear_fit_service_caches fixture resets
# fit_service._cached_peer_metrics (#106) before/after every test in the run.

DM = [
    {"Symbol": "GP", "Sector": "Telecom", "LTP": 300.0},
    {"Symbol": "ROBI", "Sector": "Telecom", "LTP": 30.0},
    {"Symbol": "BATBC", "Sector": "Telecom", "LTP": 500.0},
]
# Latest PE + volatility come from price_archive (deduped), not the datamatrix.
PRICE = [
    {"Symbol": "GP", "pe": 10.0, "vol": 0.05, "bars": 30},
    {"Symbol": "ROBI", "pe": 20.0, "vol": 0.15, "bars": 30},
    {"Symbol": "BATBC", "pe": 15.0, "vol": 0.08, "bars": 30},
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
@pytest.fixture
def wired(monkeypatch):
    def dispatch(sql, params=None):
        if "investor_profiles" in sql:
            return []                              # no profile -> neutral default
        if "SELECT Sector FROM" in sql:
            return [{"Sector": "Telecom"}]
        if "Symbol, Sector, LTP" in sql:
            return DM
        if "price_archive" in sql:
            return PRICE
        if "fundamentals_earnings" in sql:
            return EARN
        if "fundamentals_dividends" in sql:
            return DIV
        return []
    monkeypatch.setattr(db, "query_rows", dispatch)


def test_fit_for_scores_the_subject_against_its_cohort(wired):
    res = fit_service.fit_for("u1", "gp")
    assert res["symbol"] == "GP"
    axes = {a["axis"]: a for a in res["axes"]}
    assert set(axes) == {"Value", "Income", "Growth", "Stability", "Sector"}
    # GP is the cheapest (P/E 10) and least volatile of the three -> scores well.
    assert axes["Value"]["score"] is not None
    assert axes["Stability"]["score"] is not None
    assert res["composite"] is not None
    assert res["is_default_profile"] is True       # neutral profile used
    assert res["disclaimer"]


def test_thin_sector_falls_back_to_market_distribution(monkeypatch):
    # Sector read (WHERE Sector=@sector -> params present) yields 2 peers; the
    # market read (WHERE TRUE -> no params) yields 6. n<5 must fall back.
    sector_dm = [{"Symbol": "GP", "Sector": "Telecom", "LTP": 300.0},
                 {"Symbol": "ROBI", "Sector": "Telecom", "LTP": 30.0}]
    sector_price = [{"Symbol": "GP", "pe": 10.0, "vol": 0.05, "bars": 30},
                    {"Symbol": "ROBI", "pe": 20.0, "vol": 0.15, "bars": 30}]
    market_dm = sector_dm + [{"Symbol": f"S{i}", "Sector": "X", "LTP": 100.0} for i in range(5)]
    market_price = sector_price + [
        {"Symbol": f"S{i}", "pe": 5.0 + i, "vol": 0.1, "bars": 30} for i in range(5)]

    def dispatch(sql, params=None):
        market = not params
        if "investor_profiles" in sql:
            return []
        if "SELECT Sector FROM" in sql:
            return [{"Sector": "Telecom"}]
        if "Symbol, Sector, LTP" in sql:
            return market_dm if market else sector_dm
        if "price_archive" in sql:
            return market_price if market else sector_price
        return []
    monkeypatch.setattr(db, "query_rows", dispatch)

    res = fit_service.fit_for("u1", "GP")
    value = next(a for a in res["axes"] if a["axis"] == "Value")
    assert value["score"] is not None
    assert "market" in value["reason"]                 # fell back, and says so


def test_unknown_symbol_returns_all_null_axes_not_a_crash(monkeypatch):
    monkeypatch.setattr(db, "query_rows", lambda sql, params=None:
                        [] if "investor_profiles" in sql or "Sector" in sql else [])
    res = fit_service.fit_for("u1", "NOSUCH")
    assert res["symbol"] == "NOSUCH"
    assert res["composite"] is None                # nothing scored, no crash


def test_score_many_cohort_reads_are_independent_of_symbol_count(wired, monkeypatch):
    # score_many is the seam #89/#91/#93 rank through: the sector cohort is built
    # once per sector (+ at most one market fallback), NOT a per-symbol fan-out.
    # So scoring three same-sector symbols costs the same reads as scoring one.
    # (The fixture's 3-peer Telecom sector is thin — < MIN_COHORT — so this also
    # exercises the market-wide fallback: 1 sector read + 1 market read = 2.)
    calls = {"n": 0}
    orig = db.query_rows                          # the wired dispatch
    def counting(sql, params=None):
        if "price_archive" in sql:
            calls["n"] += 1
        return orig(sql, params)
    monkeypatch.setattr(db, "query_rows", counting)

    many = fit_service.score_many("u1", ["GP", "ROBI", "BATBC"])   # all Telecom
    assert set(many) == {"GP", "ROBI", "BATBC"}
    assert many["GP"]["symbol"] == "GP"
    assert calls["n"] == 2                         # 3 symbols cost no more than 1 (+ market fallback)

def test_score_many_single_symbol_matches_fit_for(wired):
    many = fit_service.score_many("u1", ["GP"])["GP"]
    one = fit_service.fit_for("u1", "GP")
    assert many["composite"] == one["composite"]
    assert [a["axis"] for a in many["axes"]] == [a["axis"] for a in one["axes"]]


def test_peer_metrics_is_cached_across_calls_for_the_same_sector_same_day(wired, monkeypatch):
    # #106: a second score_many call for the same sector, same day, should hit
    # the cache — zero further price_archive reads, not "the same as before".
    calls = {"n": 0}
    orig = db.query_rows
    def counting(sql, params=None):
        if "price_archive" in sql:
            calls["n"] += 1
        return orig(sql, params)
    monkeypatch.setattr(db, "query_rows", counting)

    fit_service.score_many("u1", ["GP", "ROBI", "BATBC"])
    assert calls["n"] == 2                         # sector read + market-fallback read
    calls["n"] = 0
    fit_service.score_many("u1", ["GP"])           # same sector, same (mocked) day
    assert calls["n"] == 0


def test_peer_metrics_cache_is_keyed_per_sector(monkeypatch):
    # A different sector must not reuse another sector's cached cohort.
    calls = {"n": 0}
    def counting(sql, params=None):
        if "price_archive" in sql:
            calls["n"] += 1
        return []
    monkeypatch.setattr(db, "query_rows", counting)

    fit_service.peer_metrics("Telecom")
    fit_service.peer_metrics("Bank")
    assert calls["n"] == 2                         # each sector queried once, independently
    fit_service.peer_metrics("Telecom")             # revisiting Telecom -> cache hit
    assert calls["n"] == 2


def test_peer_metrics_refetches_on_a_new_day(monkeypatch):
    # The cache key includes the day, so a day rollover is a fresh fetch —
    # simulated by monkeypatching the day helper rather than real time travel.
    calls = {"n": 0}
    def counting(sql, params=None):
        if "price_archive" in sql:
            calls["n"] += 1
        return []
    monkeypatch.setattr(db, "query_rows", counting)

    monkeypatch.setattr(fit_service, "_today", lambda: "2026-01-01")
    fit_service.peer_metrics("Telecom")
    assert calls["n"] == 1

    fit_service.peer_metrics("Telecom")            # same day -> cached
    assert calls["n"] == 1

    monkeypatch.setattr(fit_service, "_today", lambda: "2026-01-02")
    fit_service.peer_metrics("Telecom")             # new day -> refetched
    assert calls["n"] == 2
