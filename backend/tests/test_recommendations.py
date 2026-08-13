"""Recommendations + strategy nudges (#93). The service's BQ deps (profile,
portfolio, universe, score_many, affinity) are monkeypatched so the
generator/ranking/nudge logic tests deterministically, no BigQuery. Affinity's
own blend/threshold/caching formula (#107) has its own dedicated
test_affinity.py — here it's neutralized to the pre-#107 placeholder so ranking
order stays a pure function of fit."""
from backend import recommendation_service as rec, fit_service, affinity
from backend.models import InvestorProfile


def _profile(**kw):
    base = dict(goal="growth", risk="med", horizon="medium",
                sector_prefs=["Pharma", "Bank"], is_default=False)
    base.update(kw)
    return InvestorProfile(**base)


def _fitdict(symbol, composite, axes):
    """axes: list of (name, score, weight). Mirrors FitScore.model_dump()."""
    return {
        "symbol": symbol, "composite": composite,
        "scorable": composite is not None, "weight_caption": "",
        "is_default_profile": False, "disclaimer": "d",
        "axes": [{"axis": n, "score": s, "reason": f"{n} looks {('strong' if (s or 0) >= 60 else 'ok')}",
                  "weight": w} for n, s, w in axes],
    }


UNIVERSE = [
    {"Symbol": "BANKA", "Sector": "Bank"},      # held
    {"Symbol": "PH1", "Sector": "Pharma"},
    {"Symbol": "PH2", "Sector": "Pharma"},
    {"Symbol": "BK2", "Sector": "Bank"},
    {"Symbol": "FUEL1", "Sector": "Fuel"},      # out of preferred/affine scope
    {"Symbol": "NS1", "Sector": "Pharma"},      # non-scorable
]

# Held BANKA leans growth (Growth 60 > Income 20), volatile (Stability 30), goal-fit 40.
FITS = {
    "BANKA": _fitdict("BANKA", 40, [("Stability", 30, .3), ("Income", 20, .2), ("Growth", 60, .3)]),
    "PH1": _fitdict("PH1", 80, [("Income", 85, .4), ("Growth", 40, .2)]),
    "PH2": _fitdict("PH2", 70, [("Value", 75, .3), ("Income", 60, .3)]),
    "BK2": _fitdict("BK2", 50, [("Value", 55, .4), ("Growth", 45, .2)]),
    "NS1": _fitdict("NS1", None, [("Value", 50, .0)]),   # composite None -> not scorable
}


def _wire(monkeypatch, profile, holdings):
    monkeypatch.setattr(rec, "get_profile", lambda uid: profile)
    monkeypatch.setattr(rec, "get_portfolio", lambda uid: holdings)
    monkeypatch.setattr(rec, "_universe", lambda: UNIVERSE)
    monkeypatch.setattr(fit_service, "score_many",
                        lambda uid, syms: {s: FITS[s] for s in syms if s in FITS})
    monkeypatch.setattr(affinity, "engaged_sectors", lambda uid: [])
    monkeypatch.setattr(affinity, "affinity_score", lambda uid, sym, sector=None: 0.0)


def test_default_profile_returns_no_recs_and_a_set_profile_nudge(monkeypatch):
    _wire(monkeypatch, _profile(is_default=True), [])
    out = rec.recommend("u1")
    assert out["recs"] == []
    assert [n["kind"] for n in out["nudges"]] == ["set_profile"]
    assert out["is_default_profile"] is True


def test_recs_rank_by_fit_exclude_held_and_nonscorable(monkeypatch):
    _wire(monkeypatch, _profile(),
          [{"symbol": "BANKA", "current_price": 100.0, "quantity": 10}])
    out = rec.recommend("u1")
    syms = [r["symbol"] for r in out["recs"]]
    assert "BANKA" not in syms                       # held excluded
    assert "NS1" not in syms                          # non-scorable dropped
    assert "FUEL1" not in syms                        # out of candidate sectors
    assert syms[0] == "PH1"                           # highest composite (+ gap boost)
    assert len(out["recs"]) <= 5


def test_rec_carries_source_tags_reason_and_match_tier(monkeypatch):
    _wire(monkeypatch, _profile(),
          [{"symbol": "BANKA", "current_price": 100.0, "quantity": 10}])
    out = rec.recommend("u1")
    ph1 = next(r for r in out["recs"] if r["symbol"] == "PH1")
    assert "gap" in ph1["sources"]                    # Pharma is an unmet preference
    assert ph1["match"] == "strong"                   # composite 80
    assert ph1["reason"] and "Pharma" in ph1["reason"]
    bk2 = next(r for r in out["recs"] if r["symbol"] == "BK2")
    assert bk2["match"] == "good"                     # composite 50
    # decision C: no composite digits leak into the rendered rec
    assert "80" not in ph1["reason"]


def test_nudges_map_from_findings_and_are_additive_never_sell(monkeypatch):
    _wire(monkeypatch, _profile(),
          [{"symbol": "BANKA", "current_price": 100.0, "quantity": 10}])
    out = rec.recommend("u1")
    kinds = {n["kind"] for n in out["nudges"]}
    assert "unmet_prefs" in kinds                     # Pharma preferred, unheld
    assert "concentration" in kinds                   # 100% Bank
    assert len(out["nudges"]) <= 3
    all_syms = {s for n in out["nudges"] for s in n["symbols"]}
    assert "BANKA" not in all_syms                    # additive-only: never a held/sell symbol
    unmet = next(n for n in out["nudges"] if n["kind"] == "unmet_prefs")
    assert set(unmet["symbols"]) <= {"PH1", "PH2"}    # candidates in the unmet sector


def test_unfused_nudge_is_dropped_not_shipped_empty(monkeypatch):
    # Only preference IS the concentrated sector (Bank) -> the "spread beyond Bank"
    # nudge has no out-of-Bank candidate to fuse, so it must be dropped, not empty.
    _wire(monkeypatch, _profile(sector_prefs=["Bank"]),
          [{"symbol": "BANKA", "current_price": 100.0, "quantity": 10}])
    out = rec.recommend("u1")
    assert "concentration" not in {n["kind"] for n in out["nudges"]}
    assert all(n["symbols"] for n in out["nudges"])    # no unfused nudge ships
