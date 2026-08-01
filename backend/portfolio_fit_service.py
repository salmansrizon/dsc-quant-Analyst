"""Portfolio-level personalization (#91, spine #84): aggregate the per-holding
fit scorecard (#88) into a 'health vs your profile' read.

Six findings — concentration, holding count, risk fit, goal fit, income/growth
mix, and unmet sector preferences. Each carries a severity and a human reason;
the framing is always observation ('vs your stated preferences'), NEVER advice —
the actionable 'trim / rebalance' nudges are #93's job, over these findings.

`compute_health` is pure (profile + valued holdings + per-symbol FitScores in,
findings out) so the thresholds test against fixtures. `portfolio_health` does
the I/O: it values the holdings and scores them all through the fit engine's
`score_many` seam (#88 decision B — cohort built once), then aggregates.

Fit-derived headlines are qualitative (no score digits, per #88 decision C — the
composite is an internal ranking scalar, never a user-facing grade); structural
findings (concentration percent, holding count) keep their factual numbers.
"""
from collections import defaultdict

from google.cloud import bigquery

from . import db, fit_service
from .models import FitScore, InvestorProfile, PortfolioFinding, PortfolioHealth
from .fit_engine import DISCLAIMER
from .profile_service import get_profile
from .portfolio_service import get_portfolio

# Thresholds (engine-owned, tunable — no user-facing config). Concentration =
# top sector's value share.
_CONC = (40.0, 60.0)          # <40 good, 40..60 caution, >60 warn
_COUNT = (4, 8)               # <4 warn, 4..7 caution, >=8 good
# Minimum Stability a risk tolerance wants before volatility is a concern.
_STABILITY_TARGET = {"low": 65.0, "med": 45.0, "high": 0.0}
_GOAL = (40.0, 60.0)          # composite: <40 warn, 40..60 caution, >=60 good


def _weighted(pairs: list[tuple[float | None, float]]) -> float | None:
    """Value-weighted mean of (score, value) pairs, ignoring null scores."""
    num = sum(s * v for s, v in pairs if s is not None)
    den = sum(v for s, v in pairs if s is not None)
    return num / den if den else None


def _axis(fit: FitScore, name: str) -> float | None:
    for a in fit.axes:
        if a.axis == name:
            return a.score
    return None


def _weighted_axis(valued: list[dict], fits: dict[str, FitScore], name: str) -> float | None:
    return _weighted([(_axis(fits[h["symbol"]], name), h["value"])
                      for h in valued if h["symbol"] in fits])


def compute_health(profile: InvestorProfile, holdings: list[dict],
                   fits: dict[str, FitScore], unweighted: bool = False) -> PortfolioHealth:
    """holdings: [{symbol, sector, value}]. fits: symbol -> FitScore."""
    valued = [h for h in holdings if h.get("value")]
    total = sum(h["value"] for h in valued)
    findings: list[PortfolioFinding] = []

    # ── Concentration (structural, factual headline) ─────────────────────────
    if valued and total:
        by_sector: dict[str, float] = defaultdict(float)
        for h in valued:
            by_sector[h.get("sector") or "Unknown"] += h["value"]
        top_sector, top_val = max(by_sector.items(), key=lambda kv: kv[1])
        pct = 100.0 * top_val / total
        sev = "warn" if pct > _CONC[1] else "caution" if pct >= _CONC[0] else "good"
        findings.append(PortfolioFinding(
            kind="concentration", severity=sev, headline=f"{pct:.0f}% in {top_sector}",
            reason=(f"{top_sector} is {pct:.0f}% of your portfolio value — "
                    + ("heavily concentrated in one sector." if sev == "warn"
                       else "somewhat concentrated." if sev == "caution"
                       else "reasonably spread across sectors.")),
        ))

    # ── Holding count (structural, factual headline) ─────────────────────────
    n = len(valued)
    sev = "warn" if n < _COUNT[0] else "caution" if n < _COUNT[1] else "good"
    findings.append(PortfolioFinding(
        kind="count", severity=sev, headline=f"{n} holdings",
        reason=(f"{n} holdings — thin diversification." if sev == "warn"
                else f"{n} holdings — moderately diversified." if sev == "caution"
                else f"{n} holdings — well diversified."),
    ))

    # ── Default profile: withhold the profile-dependent findings + nudge ──────
    # (Decision: a portfolio comparative 'vs your profile' asserts something false
    #  about a user who set no profile; structural findings above still stand.)
    if profile.is_default:
        findings.append(PortfolioFinding(
            kind="risk_fit", severity="good", headline="Profile not set",
            reason="Set your investor profile to see how your holdings' risk, goal "
                   "and income/growth mix fit your preferences."))
        return PortfolioHealth(
            holdings_valued=n, total_value=round(total, 2), is_default_profile=True,
            unweighted=unweighted, findings=findings, disclaimer=DISCLAIMER)

    # ── Risk fit (value-weighted Stability vs tolerance; qualitative headline) ─
    stability = _weighted_axis(valued, fits, "Stability")
    if stability is not None:
        gap = _STABILITY_TARGET[profile.risk] - stability
        sev = "warn" if gap > 20 else "caution" if gap > 0 else "good"
        findings.append(PortfolioFinding(
            kind="risk_fit", severity=sev,
            headline=("Stability matches your profile" if sev == "good"
                      else "A little volatile for your profile" if sev == "caution"
                      else "Volatile for your risk profile"),
            reason=(f"Your holdings' volatility broadly matches your {profile.risk}-risk "
                    f"profile." if sev == "good"
                    else f"Your holdings run a little more volatile than your "
                         f"{profile.risk}-risk profile prefers." if sev == "caution"
                    else f"Your holdings skew volatile for your {profile.risk}-risk profile."),
        ))

    # ── Goal fit (value-weighted composite vs threshold; qualitative headline) ─
    composite = _weighted([(fits[h["symbol"]].composite, h["value"])
                           for h in valued if h["symbol"] in fits])
    if composite is not None:
        sev = "warn" if composite < _GOAL[0] else "caution" if composite < _GOAL[1] else "good"
        findings.append(PortfolioFinding(
            kind="goal_fit", severity=sev,
            headline=("Strong fit to your goal" if sev == "good"
                      else "Partial fit to your goal" if sev == "caution"
                      else "Weak fit to your goal"),
            reason=(f"Your holdings align well with your {profile.goal} goal." if sev == "good"
                    else f"Your holdings only partly match your {profile.goal} goal."
                    if sev == "caution"
                    else f"Your holdings sit against your {profile.goal} goal."),
        ))

    # ── Income/growth mix vs goal (value-weighted lean; qualitative headline) ─
    income_w = _weighted_axis(valued, fits, "Income")
    growth_w = _weighted_axis(valued, fits, "Growth")
    if income_w is not None and growth_w is not None:
        findings.append(_mix_finding(profile.goal, income_w, growth_w))

    # ── Unmet sector preferences ──────────────────────────────────────────────
    if profile.sector_prefs:
        held = {h.get("sector") for h in valued}
        unmet = [s for s in profile.sector_prefs if s not in held]
        if unmet:
            all_unmet = len(unmet) == len(profile.sector_prefs)
            findings.append(PortfolioFinding(
                kind="unmet_prefs", severity="warn" if all_unmet else "caution",
                headline=f"{len(unmet)} preferred sector(s) unheld",
                reason=f"You prefer {', '.join(profile.sector_prefs)} but hold "
                       f"nothing in {', '.join(unmet)}."))

    return PortfolioHealth(
        holdings_valued=n, total_value=round(total, 2), is_default_profile=False,
        unweighted=unweighted, findings=findings, disclaimer=DISCLAIMER)


def _mix_finding(goal: str, income_w: float, growth_w: float) -> PortfolioFinding:
    """Income vs growth lean of the holdings, judged against the stated goal.
    `diff` > 0 means a growth lean, < 0 an income lean."""
    diff = growth_w - income_w
    lean = "growth" if diff > 0 else "income"
    if goal == "income":
        sev = "warn" if diff > 20 else "caution" if diff > 0 else "good"
    elif goal == "growth":
        sev = "warn" if diff < -20 else "caution" if diff < 0 else "good"
    else:  # preservation — wants neither extreme
        sev = "caution" if abs(diff) > 30 else "good"
    return PortfolioFinding(
        kind="mix", severity=sev,
        headline=("Mix matches your goal" if sev == "good" else f"Holdings lean {lean}"),
        reason=(f"Your holdings' income/growth balance matches your {goal} goal." if sev == "good"
                else f"Your holdings lean {lean} while your goal is {goal}."),
    )


def _sectors_for(symbols: list[str]) -> dict[str, str | None]:
    """symbol -> sector for the held symbols, in one datamatrix read."""
    if not symbols:
        return {}
    rows = db.query_rows(
        f"""SELECT Symbol, Sector FROM {db.table_id('lankabd_datamatrix')}
            WHERE Symbol IN UNNEST(@syms)""",
        [bigquery.ArrayQueryParameter("syms", "STRING", symbols)])
    return {r["Symbol"]: r.get("Sector") for r in rows}


def portfolio_health(user_id: str) -> dict:
    profile = get_profile(user_id)
    holdings = get_portfolio(user_id)
    symbols = [h["symbol"] for h in holdings]
    sectors = _sectors_for(symbols)

    valued = [{
        "symbol": h["symbol"], "sector": sectors.get(h["symbol"]),
        "value": (h.get("current_price") or 0) * (h.get("quantity") or 0),
    } for h in holdings]

    # Equal-weight fallback: if no holding can be valued (every LTP missing),
    # weight each equally so the health read degrades to a count/mix view rather
    # than vanishing — and flag the read as unweighted.
    unweighted = bool(holdings) and not any(v["value"] for v in valued)
    if unweighted:
        for v in valued:
            v["value"] = 1.0

    # Score every holding through the shared fit seam (#88 B): cohort built once.
    scored = fit_service.score_many(user_id, symbols)
    fits = {sym: FitScore(**d) for sym, d in scored.items()}

    return compute_health(profile, valued, fits, unweighted).model_dump()
