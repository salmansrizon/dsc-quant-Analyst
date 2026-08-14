"""The fit engine (#88, personalization spine #84): score a stock against an
investor profile, explainably, as a pure function.

Five axes — Value, Income, Growth, Stability, Sector — each normalized to a 0..100
*sector percentile* (a bank's P/E is only meaningful against other banks) and
each emitting a mandatory human reason string. The investor profile sets the
per-axis weights; the composite is their weighted mean over the axes that
actually scored. A missing or meaningless metric yields a null axis that DROPS
from the composite rather than scoring 0 (a 0 would fake-penalize).

Purity is the point: `score()` takes the subject's metrics and the sector cohort
as plain data, so it unit-tests against hand-built arrays. `fit_service` owns the
BigQuery that builds those inputs. Framing is always "matches your preferences",
never advice — see DISCLAIMER.
"""
from statistics import median

from .models import FitAxis, FitScore, InvestorProfile

DISCLAIMER = (
    "Fit scores reflect how a stock matches your stated preferences — not a "
    "recommendation to buy or sell. Not financial advice."
)

# Base per-axis weights by goal (each column sums to 1). Modifiers below tilt
# these by risk tolerance and horizon; the result is renormalized over whichever
# axes end up scored.
_BASE = {
    "growth":       {"Value": .20, "Income": .15, "Growth": .30, "Stability": .15, "Sector": .20},
    "income":       {"Value": .20, "Income": .35, "Growth": .10, "Stability": .15, "Sector": .20},
    "preservation": {"Value": .20, "Income": .25, "Growth": .05, "Stability": .35, "Sector": .15},
}
# Risk tolerance scales how much the Stability axis counts: a cautious investor
# weights stability heavily; a risk-seeker barely cares. (The axis is named
# Stability — a single-stock price-dispersion proxy — not "Risk"; the profile's
# `risk` tolerance is a separate thing that tilts this axis's weight.)
_RISK_MULT = {"low": 1.6, "med": 1.0, "high": 0.5}
# Horizon tilts Growth against Income: a long horizon can ride growth, a short
# one leans on income now.
_HORIZON_MULT = {
    "short":  {"Growth": 0.7, "Income": 1.2},
    "medium": {"Growth": 1.0, "Income": 1.0},
    "long":   {"Growth": 1.3, "Income": 0.8},
}

# Below this many scored axes a composite is built on too little to mean
# anything — it floors to None and the stock is not fit-scorable (kept out of
# feed/recommendation ranking; the scorecard says so).
_MIN_SCORED_AXES = 2

_INSUFFICIENT_CAPTION = "Not enough data to fit-score this stock."


def _percentile(value: float, peers: list[float], invert: bool) -> float:
    """Where `value` sits in the peer distribution, 0..100. `invert` flips it so
    that a *lower* raw metric (cheaper P/E, lower volatility) scores higher."""
    if not peers:
        return 50.0
    below = sum(1 for p in peers if p <= value)
    pct = 100.0 * below / len(peers)
    return 100.0 - pct if invert else pct


def _tier(score: float) -> str:
    if score >= 70:
        return "strong"
    if score >= 40:
        return "moderate"
    return "weak"


def _metric_axis(
    axis: str, label: str, value, peers: list[float], invert: bool, unit: str,
    cohort_label: str = "sector",
) -> FitAxis:
    """One percentile-scored axis, or a null axis with an honest reason.

    `cohort_label` is "sector" normally, "market" when the sector was too thin
    and the percentile fell back to the market-wide distribution."""
    if value is None or not peers:
        return FitAxis(axis=axis, score=None, weight=0.0,
                       reason=f"No {label.lower()} data — {axis} not scored.")
    score = _percentile(value, peers, invert)
    med = median(peers)
    return FitAxis(
        axis=axis, score=round(score, 1), weight=0.0,
        reason=(f"{label} {value:g}{unit} vs {cohort_label} median {med:g}{unit} → "
                f"{_tier(score)} on {axis.lower()}."),
    )


def _value_axis(subject: dict, cohort: dict, labels: dict) -> FitAxis:
    """Value blends P/E and P/NAV (both cheaper-is-better), averaging whichever
    is available."""
    parts, bits = [], []
    for key, label in (("pe", "P/E"), ("pb", "P/NAV")):
        v, peers = subject.get(key), cohort.get(key, [])
        if v is not None and peers:
            parts.append(_percentile(v, peers, invert=True))
            bits.append(f"{label} {v:g} ({labels.get(key, 'sector')} median {median(peers):g})")
    if not parts:
        return FitAxis(axis="Value", score=None, weight=0.0,
                       reason="No valuation data — Value not scored.")
    score = sum(parts) / len(parts)
    return FitAxis(axis="Value", score=round(score, 1), weight=0.0,
                   reason=f"{', '.join(bits)} → {_tier(score)} on value.")


def _sector_axis(sector: str, prefs: list[str]) -> FitAxis:
    """Rank-based: the top preferred sector scores 100, decaying down the list;
    a sector not in the list scores 0; no preferences leaves it unscored."""
    if not prefs:
        return FitAxis(axis="Sector", score=None, weight=0.0,
                       reason="No sector preferences set — Sector not scored.")
    if sector in prefs:
        rank = prefs.index(sector)
        score = round(100.0 * (len(prefs) - rank) / len(prefs), 1) if len(prefs) > 1 else 100.0
        # Top choice is always a clean 100 regardless of list length.
        score = 100.0 if rank == 0 else score
        return FitAxis(axis="Sector", score=score, weight=0.0,
                       reason=f"{sector} is your #{rank + 1} preferred sector.")
    return FitAxis(axis="Sector", score=0.0, weight=0.0,
                   reason=f"{sector} isn't in your preferred sectors.")


def _weights(profile: InvestorProfile) -> dict:
    """The engine-owned weight table: base-by-goal, tilted by risk and horizon,
    normalized to sum 1 over all five axes (renormalized over scored axes later)."""
    w = dict(_BASE[profile.goal])
    w["Stability"] *= _RISK_MULT[profile.risk]
    for axis, mult in _HORIZON_MULT[profile.horizon].items():
        w[axis] *= mult
    total = sum(w.values())
    return {a: v / total for a, v in w.items()}


def score(profile: InvestorProfile, symbol: str, subject: dict, cohort: dict,
          scope: dict | None = None) -> FitScore:
    """Score `symbol` against `profile`. `subject` carries the stock's metrics
    (pe, pb, yield_, growth, volatility, sector); `cohort` the peers' arrays
    (pe, pb, yield, growth, volatility); `scope` labels each metric's cohort
    "sector" or "market" (market = the n<5 fallback), for honest reasons. All
    plain data — the engine touches no database."""
    scope = scope or {}
    axes = [
        _value_axis(subject, cohort, scope),
        _metric_axis("Income", "Dividend yield", subject.get("yield_"),
                     cohort.get("yield", []), invert=False, unit="%",
                     cohort_label=scope.get("yield", "sector")),
        _metric_axis("Growth", "EPS growth", subject.get("growth"),
                     cohort.get("growth", []), invert=False, unit="%",
                     cohort_label=scope.get("growth", "sector")),
        _metric_axis("Stability", "Volatility", subject.get("volatility"),
                     cohort.get("volatility", []), invert=True, unit="",
                     cohort_label=scope.get("volatility", "sector")),
        _sector_axis(subject.get("sector"), profile.sector_prefs),
    ]

    weights = _weights(profile)
    scored = [a for a in axes if a.score is not None]
    total_w = sum(weights[a.axis] for a in scored) or 1.0
    for a in axes:
        a.weight = round(weights[a.axis] / total_w, 4) if a.score is not None else 0.0

    # Coverage floor: a composite off fewer than two axes is noise — drop it, so
    # the stock never ranks in the feed on a single dimension.
    scorable = len(scored) >= _MIN_SCORED_AXES
    composite = (round(sum(a.score * a.weight for a in scored), 1)
                 if scorable else None)

    return FitScore(
        symbol=symbol, composite=composite, scorable=scorable,
        weight_caption=_caption(scored, scorable), axes=axes,
        is_default_profile=profile.is_default, disclaimer=DISCLAIMER,
    )


def _caption(scored: list, scorable: bool) -> str:
    """The one sentence that surfaces the profile->weight tilt (the composite is
    hidden per decision C), naming the two axes carrying the most weight. Below
    the coverage floor it carries the not-enough-data note instead."""
    if not scorable:
        return _INSUFFICIENT_CAPTION
    top = sorted(scored, key=lambda a: a.weight, reverse=True)[:2]
    names = " & ".join(a.axis for a in top)
    return f"Weighted toward {names}, from your profile."
