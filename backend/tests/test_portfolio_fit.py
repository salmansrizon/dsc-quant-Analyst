"""Portfolio health aggregation (#91) — pure compute_health over fixtures."""
from backend.portfolio_fit_service import compute_health
from backend.models import InvestorProfile, FitAxis, FitScore


def _profile(**kw):
    base = dict(goal="growth", risk="med", horizon="medium", sector_prefs=[], is_default=False)
    base.update(kw)
    return InvestorProfile(**base)


def _fit(symbol, risk=None, composite=None):
    return FitScore(symbol=symbol, composite=composite, is_default_profile=False,
                    disclaimer="d",
                    axes=[FitAxis(axis="Risk", score=risk, reason="", weight=0.0)])


def _hold(symbol, sector, value):
    return {"symbol": symbol, "sector": sector, "value": value}


def _find(health, kind):
    return next((f for f in health.findings if f.kind == kind), None)


# ── concentration ────────────────────────────────────────────────────────────

def test_concentration_warns_over_60_pct():
    h = compute_health(_profile(), [_hold("A", "Bank", 70), _hold("B", "Pharma", 30)],
                       {"A": _fit("A"), "B": _fit("B")})
    assert _find(h, "concentration").severity == "warn"

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


# ── risk fit ─────────────────────────────────────────────────────────────────

def test_low_risk_profile_warns_on_volatile_holdings():
    # low tolerance wants stability >= 65; a value-weighted 30 is far below.
    h = compute_health(_profile(risk="low"), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", risk=30)})
    assert _find(h, "risk_fit").severity == "warn"

def test_high_risk_profile_never_warns_on_volatility():
    h = compute_health(_profile(risk="high"), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", risk=10)})
    assert _find(h, "risk_fit").severity == "good"


# ── goal fit ─────────────────────────────────────────────────────────────────

def test_goal_fit_warns_on_low_composite():
    h = compute_health(_profile(goal="income"), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", risk=50, composite=20)})
    assert _find(h, "goal_fit").severity == "warn"


# ── unmet prefs ──────────────────────────────────────────────────────────────

def test_all_preferred_sectors_unheld_warns():
    h = compute_health(_profile(sector_prefs=["Pharma", "Fuel"]),
                       [_hold("A", "Bank", 100)], {"A": _fit("A", risk=50, composite=60)})
    assert _find(h, "unmet_prefs").severity == "warn"

def test_no_unmet_prefs_finding_when_all_held():
    h = compute_health(_profile(sector_prefs=["Bank"]),
                       [_hold("A", "Bank", 100)], {"A": _fit("A", risk=50, composite=60)})
    assert _find(h, "unmet_prefs") is None


# ── neutral-default softening ────────────────────────────────────────────────

def test_default_profile_softens_and_skips_fit_findings():
    h = compute_health(_profile(is_default=True), [_hold("A", "Bank", 100)],
                       {"A": _fit("A", risk=10)})
    assert h.is_default_profile is True
    assert _find(h, "goal_fit") is None
    assert _find(h, "unmet_prefs") is None
    rf = _find(h, "risk_fit")
    assert rf.severity == "good" and "profile" in rf.reason.lower()
    # profile-independent findings still present
    assert _find(h, "concentration") and _find(h, "count")
