"""Personalized recommendations + strategy nudges (#93, spine #84).

Two fused pillars over the fit engine (#88) and the portfolio read (#91):
- **Recommendations** — 'for you' unheld stocks from three generators (fit /
  behaviour / gap), unioned, ranked by fit composite (the #88 internal scalar)
  tilted by a bounded behaviour affinity + a gap-fixer boost. Top few, each with
  a reason built from its dominant fit axis. Framing is 'matches your
  preferences', never 'buy'.
- **Nudges** — the action layer over #91's findings: a deterministic map from a
  warn/caution finding to an additive, conditional-frame nudge fused with the
  candidate stocks that would ADDRESS it (never a stock to sell).

On-read Python; scores every candidate through `fit_service.score_many` (the #88
seam — cohort built once). Behaviour affinity is a placeholder seam (`affinity`,
until #86/#107); the fit + gap generators carry v1.
"""
from . import db, fit_service, affinity
from . import portfolio_fit_service as pf
from .models import FitScore, Recommendation, StrategyNudge, Recommendations
from .fit_engine import DISCLAIMER
from .profile_service import get_profile
from .portfolio_service import get_portfolio

_MAX_RECS = 5
_MAX_NUDGES = 3
_GAP_BOOST = 8.0          # ranking bump for a gap-fixing candidate
_AFFINITY_WEIGHT = 15.0   # max affinity contribution — bounded so fit stays the spine


def _universe() -> list[dict]:
    return db.query_rows(
        f"SELECT Symbol, Sector FROM {db.table_id('lankabd_datamatrix')}")


def _dominant_axis(fit: FitScore):
    """The scored axis carrying the most weight — its reason leads the rec."""
    scored = [a for a in fit.axes if a.score is not None]
    return max(scored, key=lambda a: a.weight) if scored else None


def recommend(user_id: str) -> dict:
    profile = get_profile(user_id)
    if profile.is_default:
        return Recommendations(
            recs=[], is_default_profile=True, disclaimer=DISCLAIMER,
            nudges=[StrategyNudge(
                kind="set_profile", headline="Set your investor profile",
                reason="Set your goals, risk tolerance and preferred sectors to get "
                       "recommendations matched to your preferences.",
                symbols=[])]).model_dump()

    holdings = get_portfolio(user_id)
    universe = _universe()
    sector_of = {r["Symbol"]: r.get("Sector") for r in universe}
    held = {h["symbol"] for h in holdings}
    held_sectors = {sector_of.get(s) for s in held}

    valued = [{"symbol": h["symbol"], "sector": sector_of.get(h["symbol"]),
               "value": (h.get("current_price") or 0) * (h.get("quantity") or 0)}
              for h in holdings]
    if holdings and not any(v["value"] for v in valued):
        for v in valued:
            v["value"] = 1.0

    # Candidate sectors: preferred ∪ engaged(behaviour) ∪ unmet-preference.
    # Empty (no prefs, no affinity yet) → the whole market, ranked purely on fit.
    engaged = affinity.engaged_sectors(user_id)
    unmet = [s for s in profile.sector_prefs if s not in held_sectors]
    cand_sectors = set(profile.sector_prefs) | set(engaged) | set(unmet)
    candidates = [r["Symbol"] for r in universe
                  if r["Symbol"] not in held
                  and (not cand_sectors or r.get("Sector") in cand_sectors)]

    # Score held + candidates in one seam call (cohort built once, #88 B).
    fits_raw = fit_service.score_many(user_id, list(held | set(candidates)))
    fits = {s: FitScore(**d) for s, d in fits_raw.items()}
    held_fits = {s: fits[s] for s in held if s in fits}

    ranked = _rank(user_id, candidates, sector_of, profile, engaged, unmet, fits)
    recs = _recs(ranked, profile, unmet)
    nudges = _nudges(profile, valued, held_fits, unmet, ranked)

    return Recommendations(recs=recs, nudges=nudges,
                           is_default_profile=False, disclaimer=DISCLAIMER).model_dump()


def _rank(user_id, candidates, sector_of, profile, engaged, unmet, fits):
    """Scorable candidates ordered by fit-composite spine + bounded affinity tilt
    + gap boost. Returns [(sym, sector, fit, sources)]."""
    ranked = []
    for sym in candidates:
        fit = fits.get(sym)
        if not fit or not fit.scorable or fit.composite is None:
            continue                                    # drop non-scorable (<2-axis floor)
        sec = sector_of.get(sym)
        sources = []
        if sec in profile.sector_prefs:
            sources.append("fit")
        if sec in engaged:
            sources.append("behaviour")
        if sec in unmet:
            sources.append("gap")
        sources = sources or ["fit"]
        boost = (_GAP_BOOST if "gap" in sources else 0.0) \
            + _AFFINITY_WEIGHT * affinity.affinity_score(user_id, sym, sec)
        ranked.append((fit.composite + boost, sym, sec, fit, sources))
    ranked.sort(key=lambda t: t[0], reverse=True)
    return [(sym, sec, fit, sources) for _, sym, sec, fit, sources in ranked]


def _recs(ranked, profile, unmet) -> list[Recommendation]:
    recs = []
    for sym, sec, fit, sources in ranked[:_MAX_RECS]:
        dom = _dominant_axis(fit)
        note = (f"in your preferred {sec} sector" if sec in profile.sector_prefs
                else f"fills your unheld {sec} preference" if sec in unmet
                else f"matches your {profile.goal} goal")
        reason = (f"{dom.reason} — {note}." if dom
                  else f"Matches your {profile.goal} goal — {note}.")
        recs.append(Recommendation(
            symbol=sym, sector=sec,
            match="strong" if fit.composite >= 60 else "good",
            reason=reason, sources=sources))
    return recs


def _nudges(profile, valued, held_fits, unmet, ranked) -> list[StrategyNudge]:
    """Deterministic map from #91 warn/caution findings to additive, conditional
    -frame nudges fused with the candidates that address each. Priority order,
    capped at _MAX_NUDGES. Symbols are always unheld candidates — never a sell; a
    nudge that can't fuse any candidate is dropped rather than shipped unfused."""
    findings = {f.kind: f for f in pf.compute_health(profile, valued, held_fits).findings}
    cands = [(sym, sec, fit) for sym, sec, fit, _ in ranked]
    out: list[StrategyNudge] = []

    f = findings.get("unmet_prefs")
    if f and f.severity in ("warn", "caution"):
        out.append(StrategyNudge(
            kind="unmet_prefs", headline=f"Explore your preferred {', '.join(unmet)}",
            reason=f"You prefer {', '.join(unmet)} but hold nothing there — these fit "
                   f"your profile in those sectors.",
            symbols=[s for s, sec, _ in cands if sec in unmet][:3]))

    f = findings.get("concentration")
    if f and f.severity in ("warn", "caution"):
        by = pf.sector_values(valued)
        top_sector = max(by, key=by.get) if by else None
        out.append(StrategyNudge(
            kind="concentration", headline=f"Spread beyond {top_sector}",
            reason=f"Your portfolio leans heavily to {top_sector}; adding names in "
                   f"other sectors would reduce that concentration.",
            symbols=[s for s, sec, _ in cands if sec != top_sector][:3]))

    f = findings.get("mix")
    if f and f.severity in ("warn", "caution"):
        income_w = pf.weighted_axis(valued, held_fits, "Income") or 0.0
        growth_w = pf.weighted_axis(valued, held_fits, "Growth") or 0.0
        lean = "growth" if growth_w > income_w else "income"
        opp = "Income" if lean == "growth" else "Growth"
        tilted = sorted(cands, key=lambda t: pf.axis_score(t[2], opp) or 0.0, reverse=True)
        out.append(StrategyNudge(
            kind="mix", headline=f"Balance your {lean}-leaning mix",
            reason=f"Your holdings lean {lean} while your goal is {profile.goal}; adding "
                   f"{opp.lower()}-tilted names would balance the mix.",
            symbols=[s for s, sec, fit in tilted if (pf.axis_score(fit, opp) or 0) > 0][:3]))

    f = findings.get("goal_fit")
    if f and f.severity in ("warn", "caution"):
        out.append(StrategyNudge(
            kind="goal_fit", headline=f"Names that fit your {profile.goal} goal",
            reason=f"Your holdings only partly match your {profile.goal} goal; these fit "
                   f"it more closely.",
            symbols=[s for s, sec, _ in cands][:3]))

    # A nudge with no candidate to fuse is an unfused observation (#91 already
    # shows it) — drop it; keep only nudges that actually suggest names.
    return [n for n in out if n.symbols][:_MAX_NUDGES]
