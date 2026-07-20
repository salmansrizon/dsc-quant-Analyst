"""Portfolio-level personalization (#91, spine #84): aggregate the per-holding
fit scorecard (#88) into a 'health vs your profile' read.

Four findings — concentration, holding count, risk fit, goal fit — plus unmet
sector preferences. Each carries a severity and a human reason; the framing is
always 'vs your stated preferences', never advice.

`compute_health` is pure (profile + valued holdings + per-symbol FitScores in,
findings out) so the thresholds test against fixtures. `portfolio_health` does
the I/O: it values the holdings, builds each distinct sector's cohort ONCE
(batched, shared market fallback), and scores every holding against it.
"""
from collections import defaultdict

from google.cloud import bigquery

from . import db, fit_service
from .fit_service import MarketCache, build_cohort, score_symbol
from .models import FitScore, InvestorProfile, PortfolioFinding, PortfolioHealth
from .fit_engine import DISCLAIMER
from .profile_service import get_profile
from .portfolio_service import get_portfolio

# Thresholds (engine-owned, tunable). Concentration = top sector's value share.
_CONC = (40.0, 60.0)          # <40 good, 40..60 caution, >60 warn
_COUNT = (4, 8)               # <4 warn, 4..7 caution, >=8 good
# Stability (Risk axis) a tolerance wants at minimum before it's a concern.
_STABILITY_TARGET = {"low": 65.0, "med": 45.0, "high": 0.0}
_GOAL = (40.0, 60.0)          # composite: <40 warn, 40..60 caution, >=60 good


def _weighted(pairs: list[tuple[float, float]]) -> float | None:
    """Value-weighted mean of (score, value) pairs, ignoring null scores."""
    num = sum(s * v for s, v in pairs if s is not None)
    den = sum(v for s, v in pairs if s is not None)
    return num / den if den else None


def _risk_axis(fit: FitScore) -> float | None:
    for a in fit.axes:
        if a.axis == "Risk":
            return a.score
    return None


def compute_health(profile: InvestorProfile, holdings: list[dict],
                   fits: dict[str, FitScore]) -> PortfolioHealth:
    """holdings: [{symbol, sector, value}]. fits: symbol -> FitScore."""
    valued = [h for h in holdings if h.get("value")]
    total = sum(h["value"] for h in valued)
    findings: list[PortfolioFinding] = []

    # ── Concentration (profile-independent) ──────────────────────────────────
    if valued and total:
        by_sector: dict[str, float] = defaultdict(float)
        for h in valued:
            by_sector[h.get("sector") or "Unknown"] += h["value"]
        top_sector, top_val = max(by_sector.items(), key=lambda kv: kv[1])
        pct = 100.0 * top_val / total
        sev = "warn" if pct > _CONC[1] else "caution" if pct >= _CONC[0] else "good"
        findings.append(PortfolioFinding(
            kind="concentration", severity=sev,
            headline=f"{pct:.0f}% in {top_sector}",
            reason=(f"{top_sector} is {pct:.0f}% of your portfolio value — "
                    + ("heavily concentrated." if sev == "warn"
                       else "somewhat concentrated." if sev == "caution"
                       else "reasonably spread across sectors.")),
        ))

    # ── Holding count (profile-independent) ──────────────────────────────────
    n = len(valued)
    sev = "warn" if n < _COUNT[0] else "caution" if n < _COUNT[1] else "good"
    findings.append(PortfolioFinding(
        kind="count", severity=sev, headline=f"{n} holdings",
        reason=(f"{n} holdings — thin diversification." if sev == "warn"
                else f"{n} holdings — moderately diversified." if sev == "caution"
                else f"{n} holdings — well diversified."),
    ))

    # ── Risk / goal fit + unmet prefs (profile-dependent) ────────────────────
    if profile.is_default:
        findings.append(PortfolioFinding(
            kind="risk_fit", severity="good", headline="Profile not set",
            reason="Set your investor profile to see how your holdings' risk and "
                   "goal fit your preferences."))
        return PortfolioHealth(
            holdings_valued=n, total_value=round(total, 2),
            is_default_profile=True, findings=findings, disclaimer=DISCLAIMER)

    stability = _weighted([(_risk_axis(fits[h["symbol"]]), h["value"])
                           for h in valued if h["symbol"] in fits])
    if stability is not None:
        target = _STABILITY_TARGET[profile.risk]
        gap = target - stability
        sev = "warn" if gap > 20 else "caution" if gap > 0 else "good"
        findings.append(PortfolioFinding(
            kind="risk_fit", severity=sev,
            headline=f"Stability {stability:.0f}/100",
            reason=(f"Your holdings' volatility skews high for your {profile.risk}-risk "
                    f"profile." if sev == "warn"
                    else f"Your holdings' risk broadly matches your {profile.risk}-risk profile."
                    if sev == "good"
                    else f"Your holdings run a little more volatile than your "
                         f"{profile.risk}-risk profile prefers."),
        ))

    composite = _weighted([(fits[h["symbol"]].composite, h["value"])
                           for h in valued if h["symbol"] in fits])
    if composite is not None:
        sev = "warn" if composite < _GOAL[0] else "caution" if composite < _GOAL[1] else "good"
        findings.append(PortfolioFinding(
            kind="goal_fit", severity=sev,
            headline=f"Goal fit {composite:.0f}/100",
            reason=(f"Your holdings align well with your {profile.goal} goal." if sev == "good"
                    else f"Your holdings only partly match your {profile.goal} goal."
                    if sev == "caution"
                    else f"Your holdings sit against your {profile.goal} goal."),
        ))

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
        holdings_valued=n, total_value=round(total, 2),
        is_default_profile=False, findings=findings, disclaimer=DISCLAIMER)


def _sectors_for(symbols: list[str]) -> dict[str, str]:
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
    # than vanishing (decision Q3).
    if holdings and not any(v["value"] for v in valued):
        for v in valued:
            v["value"] = 1.0

    # Batch: build each distinct sector's cohort once, score every holding in it.
    market = MarketCache()
    by_sector: dict[str | None, list[str]] = defaultdict(list)
    for h in valued:
        by_sector[h["sector"]].append(h["symbol"])
    fits = {}
    for sector, syms in by_sector.items():
        peers = build_cohort(sector) if sector else {}
        for sym in syms:
            fits[sym] = score_symbol(profile, sym, sector, peers, market)

    return compute_health(profile, valued, fits).model_dump()
