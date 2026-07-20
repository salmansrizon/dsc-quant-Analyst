"""Wires the pure fit engine (#88) to BigQuery: builds a stock's metrics and its
sector cohort, then hands both to `fit_engine.score`.

The cohort is built by BULK queries per sector — a handful of aggregate reads,
never a per-symbol fan-out of `get_fundamentals` (that would be N×several queries
a scorecard). Every peer's metric is derived in Python by the SAME `valuation`
functions the single-stock path uses, so the subject is compared like-for-like.

When a sector has too few peers for a percentile to mean anything (< MIN_COHORT),
each thin metric falls back to the market-wide distribution — the fallback the
decision called for.
"""
from collections import defaultdict

from google.cloud import bigquery

from . import db, valuation
from .fit_engine import score as engine_score
from .models import InvestorProfile
from .profile_service import get_profile

# How many recent daily bars back the volatility proxy — the coefficient of
# variation of close (STDDEV/AVG). A cheap, cohort-consistent stand-in for
# return volatility; beta is unavailable (no market-index series landed).
_VOL_BARS = 30
_VOL_MIN = 5

# Below this many peers a sector percentile is noise; fall back to the market.
MIN_COHORT = 5

# The engine's cohort keys mapped to the subject metric keys they percentile.
_METRIC_KEYS = {"pe": "pe", "pb": "pb", "yield": "yield_",
                "growth": "growth", "volatility": "volatility"}


def _sector_of(symbol: str) -> str | None:
    rows = db.query_rows(
        f"SELECT Sector FROM {db.table_id('lankabd_datamatrix')} WHERE Symbol = @s LIMIT 1",
        [bigquery.ScalarQueryParameter("s", "STRING", symbol)],
    )
    return rows[0]["Sector"] if rows else None


def _peer_metrics(sector: str | None) -> dict[str, dict]:
    """Every symbol in `sector` (or the whole market when `sector` is None), each
    with its derived fit metrics — the same figures `get_fundamentals` computes,
    but for the cohort in a handful of reads.

    PE and volatility come from `price_archive` (the archive carries the daily
    valuation columns; the datamatrix's PE columns only exist after a widened
    re-scrape — see market_service). Symbols are scoped by the datamatrix
    universe, not by a Sector column on the archive, which it does not carry.
    """
    params, where = [], "TRUE"
    if sector is not None:
        params = [bigquery.ScalarQueryParameter("sector", "STRING", sector)]
        where = "Sector = @sector"

    dm = db.query_rows(
        f"SELECT Symbol, Sector, LTP FROM {db.table_id('lankabd_datamatrix')} WHERE {where}",
        params)
    earn = db.query_rows(
        f"""SELECT symbol, year, eps, nav FROM {db.current_view('fundamentals_earnings')}
            WHERE period = 'ANNUAL'""")
    divs = db.query_rows(
        f"""SELECT symbol, year, dividend_type, cash_dividend_pct, publish_date
            FROM {db.current_view('fundamentals_dividends')}""")
    # Latest PE + coefficient-of-variation volatility per symbol, deduped (the
    # archive stores each (Symbol, Date) twice) and scoped to the cohort's
    # symbols via the datamatrix.
    price = db.query_rows(
        f"""
        SELECT Symbol,
               ANY_VALUE(IF(rn = 1, COALESCE(Forward_PE, Audited_PE), NULL)) AS pe,
               SAFE_DIVIDE(STDDEV(IF(rn <= {_VOL_BARS}, Close, NULL)),
                           AVG(IF(rn <= {_VOL_BARS}, Close, NULL))) AS vol,
               COUNTIF(rn <= {_VOL_BARS}) AS bars
        FROM (
          SELECT Symbol, Close, Forward_PE, Audited_PE,
                 ROW_NUMBER() OVER (PARTITION BY Symbol ORDER BY Date DESC) AS rn
          FROM (
            SELECT DISTINCT Symbol, Date, Close, Forward_PE, Audited_PE
            FROM {db.table_id('lankabd_price_archive')}
            WHERE Symbol IN (SELECT Symbol FROM {db.table_id('lankabd_datamatrix')} WHERE {where})
          )
        )
        GROUP BY Symbol
        """, params)

    eps_by_symbol: dict[str, dict[int, float]] = defaultdict(dict)
    nav_by_symbol: dict[str, tuple[int, float]] = {}
    for r in earn:
        sym, yr = r["symbol"], r["year"]
        if r.get("eps") is not None:
            eps_by_symbol[sym][yr] = r["eps"]
        if r.get("nav") is not None and (sym not in nav_by_symbol or yr > nav_by_symbol[sym][0]):
            nav_by_symbol[sym] = (yr, r["nav"])
    decls_by_symbol: dict[str, list[dict]] = defaultdict(list)
    for r in divs:
        decls_by_symbol[r["symbol"]].append(r)
    price_by_symbol = {r["Symbol"]: r for r in price}

    out: dict[str, dict] = {}
    for r in dm:
        sym = r["Symbol"]
        ltp = r.get("LTP")
        pr = price_by_symbol.get(sym, {})
        pe = pr.get("pe")
        vol = pr.get("vol") if (pr.get("bars") or 0) >= _VOL_MIN else None
        nav = nav_by_symbol.get(sym, (None, None))[1]
        decls = decls_by_symbol.get(sym, [])
        div_year = valuation.latest_complete_dividend_year(decls)
        cash = valuation.annual_cash_dividend(decls, div_year) if div_year else None
        out[sym] = {
            "sector": r.get("Sector"),
            "pe": pe if (pe and pe > 0) else None,
            "pb": valuation.price_to_book(ltp, nav),
            "yield_": valuation.dividend_yield(cash, ltp),
            "growth": valuation.eps_growth(eps_by_symbol.get(sym, {})),
            "volatility": vol,
        }
    return out


def _arrays(peers: dict[str, dict]) -> dict[str, list[float]]:
    return {
        ck: [m[sk] for m in peers.values() if m.get(sk) is not None]
        for ck, sk in _METRIC_KEYS.items()
    }


class _MarketCache:
    """Lazily builds the whole-market peer set once, then reuses it — so a
    portfolio scoring many thin sectors pays for the market fallback at most
    once, not per sector."""
    def __init__(self):
        self._peers: dict | None = None

    def peers(self) -> dict:
        if self._peers is None:
            self._peers = _peer_metrics(None)
        return self._peers


def score_symbol(profile: InvestorProfile, symbol: str, sector: str | None,
                 sector_peers: dict, market: "_MarketCache"):
    """Score one symbol against its (already-built) sector cohort, falling back
    to the market-wide distribution for any metric with fewer than MIN_COHORT
    peers. Shared by the single-stock and portfolio paths so scoring lives once.
    """
    sector_arrays = _arrays(sector_peers)
    cohort: dict[str, list[float]] = {}
    scope: dict[str, str] = {}
    for ck in _METRIC_KEYS:
        arr = sector_arrays.get(ck, [])
        if len(arr) < MIN_COHORT:
            marr = _arrays(market.peers()).get(ck, [])
            if len(marr) > len(arr):
                cohort[ck], scope[ck] = marr, "market"
                continue
        cohort[ck], scope[ck] = arr, "sector"

    subject = sector_peers.get(symbol) or market.peers().get(symbol) or {
        "sector": sector, "pe": None, "pb": None, "yield_": None,
        "growth": None, "volatility": None,
    }
    return engine_score(profile, symbol, subject, cohort, scope)


def fit_for(user_id: str, symbol: str) -> dict:
    """The scorecard for one stock against one user's profile."""
    symbol = symbol.upper()
    profile = get_profile(user_id)
    sector = _sector_of(symbol)
    peers = _peer_metrics(sector) if sector else {}
    return score_symbol(profile, symbol, sector, peers, _MarketCache()).model_dump()
