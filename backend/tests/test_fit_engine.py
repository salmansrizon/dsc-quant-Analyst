"""Pure fit engine (#88): profile + subject metrics + sector cohort -> scorecard.

No BigQuery here — the engine is a pure function; the service (test_fit_service /
integration) owns the queries. Cohorts are hand-built arrays.
"""
from backend import fit_engine as fe
from backend.models import InvestorProfile, FitScore


def _profile(**kw) -> InvestorProfile:
    base = dict(goal="growth", risk="med", horizon="medium", sector_prefs=[], is_default=False)
    base.update(kw)
    return InvestorProfile(**base)


# Peers chosen so the subject sits at a known percentile.
COHORT = {
    "pe": [5, 10, 15, 20, 25],          # lower = cheaper (inverted)
    "pb": [1, 2, 3, 4, 5],              # lower = cheaper (inverted)
    "yield": [1, 2, 3, 4, 5],          # higher = better
    "growth": [0, 5, 10, 15, 20],      # higher = better
    "volatility": [1, 2, 3, 4, 5],     # lower = more stable (inverted)
}


def _subject(**kw):
    base = dict(sector="Bank", pe=None, pb=None, yield_=None, growth=None, volatility=None)
    base.update(kw)
    return base


# ── normalization / direction ───────────────────────────────────────────────

def test_low_pe_scores_high_on_value():
    s = fe.score(_profile(), "GP", _subject(pe=5, pb=1), COHORT)
    value = next(a for a in s.axes if a.axis == "Value")
    assert value.score is not None and value.score >= 80        # cheapest peer

def test_high_pe_scores_low_on_value():
    s = fe.score(_profile(), "GP", _subject(pe=25, pb=5), COHORT)
    value = next(a for a in s.axes if a.axis == "Value")
    assert value.score is not None and value.score <= 20

def test_high_yield_scores_high_on_income_with_median_in_reason():
    s = fe.score(_profile(goal="income"), "GP", _subject(yield_=5), COHORT)
    inc = next(a for a in s.axes if a.axis == "Income")
    assert inc.score >= 80
    assert "3" in inc.reason                                    # sector median = 3


# ── null / guard handling ───────────────────────────────────────────────────

def test_missing_metric_yields_null_axis_dropped_from_composite():
    # Income missing; Value + Growth still score (>= the 2-axis floor).
    s = fe.score(_profile(goal="income"), "GP",
                 _subject(yield_=None, pe=10, pb=2, growth=10), COHORT)
    inc = next(a for a in s.axes if a.axis == "Income")
    assert inc.score is None
    assert "not scored" in inc.reason.lower() or "no " in inc.reason.lower()
    # composite still computed from the axes that did score
    assert s.composite is not None


# ── weights ─────────────────────────────────────────────────────────────────

def test_income_goal_weights_income_axis_highest():
    s = fe.score(_profile(goal="income"), "GP",
                 _subject(pe=10, pb=2, yield_=4, growth=10, volatility=3), COHORT)
    w = {a.axis: a.weight for a in s.axes}
    assert w["Income"] == max(w.values())

def test_low_risk_tolerance_weights_stability_axis_up():
    lo = fe.score(_profile(risk="low"), "GP",
                  _subject(pe=10, pb=2, yield_=4, growth=10, volatility=3), COHORT)
    hi = fe.score(_profile(risk="high"), "GP",
                  _subject(pe=10, pb=2, yield_=4, growth=10, volatility=3), COHORT)
    wl = next(a.weight for a in lo.axes if a.axis == "Stability")
    wh = next(a.weight for a in hi.axes if a.axis == "Stability")
    assert wl > wh

def test_axis_weights_sum_to_one_over_scored_axes():
    s = fe.score(_profile(), "GP",
                 _subject(pe=10, pb=2, yield_=4, growth=10, volatility=3), COHORT)
    scored = [a.weight for a in s.axes if a.score is not None]
    assert abs(sum(scored) - 1.0) < 1e-6


# ── sector match ─────────────────────────────────────────────────────────────

def test_top_ranked_sector_scores_high():
    s = fe.score(_profile(sector_prefs=["Bank", "Pharma"]), "GP",
                 _subject(pe=10), COHORT)
    sm = next(a for a in s.axes if a.axis == "Sector")
    assert sm.score == 100                                      # #1 pref

def test_sector_not_in_prefs_scores_low():
    s = fe.score(_profile(sector_prefs=["Pharma"]), "GP", _subject(pe=10), COHORT)
    sm = next(a for a in s.axes if a.axis == "Sector")
    assert sm.score == 0

def test_default_profile_marks_flag_and_returns_fitscore():
    s = fe.score(_profile(is_default=True, sector_prefs=[]), "GP",
                 _subject(pe=10, yield_=4), COHORT)
    assert isinstance(s, FitScore)
    assert s.is_default_profile is True
    assert s.disclaimer                                         # not-advice framing present


# ── Stability axis (renamed from Risk; math unchanged) ───────────────────────

def test_stability_axis_replaces_risk():
    s = fe.score(_profile(), "GP",
                 _subject(pe=10, pb=2, yield_=4, growth=10, volatility=3), COHORT)
    names = {a.axis for a in s.axes}
    assert names == {"Value", "Income", "Growth", "Stability", "Sector"}

def test_low_volatility_scores_high_on_stability():
    s = fe.score(_profile(), "GP", _subject(volatility=1), COHORT)   # least volatile
    st = next(a for a in s.axes if a.axis == "Stability")
    assert st.score is not None and st.score >= 80


# ── composite hidden-but-computed + coverage floor ───────────────────────────

def test_two_scored_axes_are_scorable_with_composite():
    s = fe.score(_profile(), "GP", _subject(pe=10, pb=2, yield_=4), COHORT)
    assert s.scorable is True
    assert s.composite is not None

def test_fewer_than_two_scored_axes_floors_composite_to_none():
    # Only Income scores; everything else null -> below the 2-axis floor.
    s = fe.score(_profile(sector_prefs=[]), "GP", _subject(yield_=4), COHORT)
    scored = [a for a in s.axes if a.score is not None]
    assert len(scored) == 1
    assert s.scorable is False
    assert s.composite is None
    assert "not enough data" in s.weight_caption.lower()


# ── weight caption (only place profile->weight link surfaces) ─────────────────

def test_weight_caption_names_the_top_weighted_axes():
    s = fe.score(_profile(goal="income"), "GP",
                 _subject(pe=10, pb=2, yield_=4, growth=10, volatility=3), COHORT)
    assert "Income" in s.weight_caption
    assert "your profile" in s.weight_caption.lower()
