"""Portfolio health aggregation (#91) — pure compute_health over fixtures, plus
the score_many-backed I/O path. Rebuilt on the #88 seam: reads the Stability
axis (not "Risk"), adds the income/growth-mix finding, and asserts fit-derived
headlines carry no score digits (#88 decision C)."""
from backend import db, portfolio_fit_service
from backend.portfolio_fit_service import compute_health
from backend.models import InvestorProfile, FitAxis, FitScore


def _profile(**kw):
    base = dict(goal="growth", risk="med", horizon="medium", sector_prefs=[], is_default=False)
    base.update(kw)
    return InvestorProfile(**base)


def _fit(symbol, stability=None, composite=None, income=None, growth=None):
    axes = [FitAxis(axis="Stability", score=stability, reason="", weight=0.0)]
    if income is not None:
        axes.append(FitAxis(axis="Income", score=income, reason="", weight=0.0))
    if growth is not None:
        axes.append(FitAxis(axis="Growth", score=growth, reason="", weight=0.0))
    return FitScore(symbol=symbol, composite=composite, is_default_profile=False,
                    disclaimer="d", axes=axes)


def _hold(symbol, sector, value):
    return {"symbol": symbol, "sector": sector, "value": value}


def _find(health, kind):
    return next((f for f in health.findings if f.kind == kind), None)


# ── concentration (structural, factual headline) ─────────────────────────────

def test_concentration_warns_over_60_pct():
    h = compute_health(_profile(), [_hold("A", "Bank", 70), _hold("B", "Pharma", 30)],
                       {"A": _fit("A"), "B": _fit("B")})
    c = _find(h, "concentration")
    assert c.severity == "warn"
    assert "70%" in c.headline                       # structural findings keep numbers

def test_concentration_good_when_spread():
    h = compute_health(_profile(),
                       [_hold("A", "Bank", 25), _hold("B", "Pharma", 25),
                        _hold("C", "Fuel", 25), _hold("D", "Food", 25)],
                       {s: _fit(s) for s in "ABCD"})
    assert _find(h, "concentration").severity == "good"


# ── count ────────────────────────────────────────────────────────────────────

def test_count_warns_under_four():
    h = compute_health(_profile(), [_hold("A", "Bank", 10)], {"A": _fit("A")})
    assert _find(h, "count").severity == "warn"

def test_count_good_at_eight():
    holds = [_hold(str(i), "Bank", 10) for i in range(8)]
    h = compute_health(_profile(), holds, {str(i): _fit(str(i)) for i in range(8)})
    assert _find(h, "count").severity == "good"


# ── risk fit (Stability axis; qualitative headline, no digits) ───────────────

def test_low_risk_profile_warns_on_volatile_holdings():
    # low tolerance wants Stability >= 65; a value-weighted 30 is far below.
    h = compute_health(_profile(risk="low"), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", stability=30)})
    rf = _find(h, "risk_fit")
    assert rf.severity == "warn"
    assert not any(ch.isdigit() for ch in rf.headline)   # no score digits (decision C)

def test_high_risk_profile_never_warns_on_volatility():
    h = compute_health(_profile(risk="high"), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", stability=10)})
    assert _find(h, "risk_fit").severity == "good"


# ── goal fit (composite; qualitative headline) ───────────────────────────────

def test_goal_fit_warns_on_low_composite():
    h = compute_health(_profile(goal="income"), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", stability=50, composite=20)})
    gf = _find(h, "goal_fit")
    assert gf.severity == "warn"
    assert not any(ch.isdigit() for ch in gf.headline)


# ── income/growth mix vs goal (NEW) ──────────────────────────────────────────

def test_mix_warns_when_growth_leaning_against_income_goal():
    h = compute_health(_profile(goal="income"), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", stability=50, composite=60, income=20, growth=80)})
    mix = _find(h, "mix")
    assert mix.severity == "warn"
    assert "lean" in mix.headline.lower()

def test_mix_good_when_growth_leaning_matches_growth_goal():
    h = compute_health(_profile(goal="growth"), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", stability=50, composite=60, income=20, growth=80)})
    assert _find(h, "mix").severity == "good"

def test_no_mix_finding_without_income_and_growth_axes():
    h = compute_health(_profile(), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", stability=50, composite=60)})
    assert _find(h, "mix") is None


# ── unmet prefs ──────────────────────────────────────────────────────────────

def test_all_preferred_sectors_unheld_warns():
    h = compute_health(_profile(sector_prefs=["Pharma", "Fuel"]),
                       [_hold("A", "Bank", 100)], {"A": _fit("A", stability=50, composite=60)})
    assert _find(h, "unmet_prefs").severity == "warn"

def test_no_unmet_prefs_finding_when_all_held():
    h = compute_health(_profile(sector_prefs=["Bank"]),
                       [_hold("A", "Bank", 100)], {"A": _fit("A", stability=50, composite=60)})
    assert _find(h, "unmet_prefs") is None


# ── default profile: withhold profile-dependent findings + nudge ─────────────

def test_default_profile_withholds_fit_findings_and_nudges():
    h = compute_health(_profile(is_default=True), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", stability=10)})
    assert h.is_default_profile is True
    assert _find(h, "goal_fit") is None and _find(h, "mix") is None
    assert _find(h, "unmet_prefs") is None
    rf = _find(h, "risk_fit")
    assert rf.severity == "good" and "profile" in rf.reason.lower()
    # structural findings still present
    assert _find(h, "concentration") and _find(h, "count")


# ── equal-weight fallback (all LTP missing) + score_many I/O path ────────────

def test_equal_weight_fallback_flags_unweighted(monkeypatch):
    def dispatch(sql, params=None):
        if "p.symbol" in sql:                              # get_portfolio
            return [{"symbol": "GP", "current_price": None, "quantity": 10},
                    {"symbol": "ROBI", "current_price": None, "quantity": 5}]
        if "investor_profiles" in sql:
            return []                                      # neutral default
        if "UNNEST" in sql:                                # _sectors_for
            return [{"Symbol": "GP", "Sector": "Bank"},
                    {"Symbol": "ROBI", "Sector": "Bank"}]
        return []                                          # score_many cohort reads -> empty
    monkeypatch.setattr(db, "query_rows", dispatch)

    health = portfolio_fit_service.portfolio_health("u1")
    # Holdings had no price, but equal-weighting still values + reports them.
    assert health["holdings_valued"] == 2
    assert health["unweighted"] is True
    kinds = {f["kind"] for f in health["findings"]}
    assert {"concentration", "count"} <= kinds
