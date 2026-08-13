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


def sector_of(symbol: str) -> str | None:
    rows = db.query_rows(
        f"SELECT Sector FROM {db.table_id('lankabd_datamatrix')} WHERE Symbol = @s LIMIT 1",
        [bigquery.ScalarQueryParameter("s", "STRING", symbol)],
    )
    return rows[0]["Sector"] if rows else None


def peer_metrics(sector: str | None) -> dict[str, dict]:
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


def _cohort(peers: dict[str, dict], market: "_MarketCache") -> tuple[dict, dict]:
    """Build the engine's cohort arrays + their scope labels from a sector's peers,
    filling any thin metric (< MIN_COHORT) from the market-wide distribution
    (decision: n < 5). `market` is a lazy, once-built market cohort shared across
    every symbol in a batch."""
    sector_arrays = _arrays(peers)
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
    return cohort, scope


class _MarketCache:
    """Builds the market-wide peer set at most once per request, however many
    sectors and symbols end up needing the n<5 fallback."""
    def __init__(self):
        self._peers: dict[str, dict] | None = None

    def peers(self) -> dict[str, dict]:
        if self._peers is None:
            self._peers = peer_metrics(None)
        return self._peers


def _null_subject(sector: str | None) -> dict:
    # Keys derived from _METRIC_KEYS so a new metric is added in one place.
    return {"sector": sector, **{sk: None for sk in _METRIC_KEYS.values()}}


def fit_for(user_id: str, symbol: str) -> dict:
    """The scorecard for one stock against one user's profile."""
    return score_many(user_id, [symbol])[symbol.upper()]


def score_many(user_id: str, symbols: list[str]) -> dict[str, dict]:
    """Score many stocks against one profile — the seam #89 (feed) / #91
    (portfolio) / #93 (recommendations) rank through. The sector cohort is built
    ONCE per sector (not a per-symbol fan-out), and the market fallback at most
    once for the whole batch. Returns {SYMBOL: FitScore-dict}."""
    symbols = [s.upper() for s in symbols]
    profile = get_profile(user_id)
    market = _MarketCache()

    sector_by_symbol: dict[str, str | None] = {}
    peers_by_sector: dict[str | None, dict[str, dict]] = {}
    cohort_by_sector: dict[str | None, tuple[dict, dict]] = {}
    out: dict[str, dict] = {}
    for symbol in symbols:
        if symbol not in sector_by_symbol:
            sector_by_symbol[symbol] = sector_of(symbol)
        sector = sector_by_symbol[symbol]
        if sector not in peers_by_sector:
            peers_by_sector[sector] = peer_metrics(sector) if sector else {}
            cohort_by_sector[sector] = _cohort(peers_by_sector[sector], market)
        peers = peers_by_sector[sector]
        cohort, scope = cohort_by_sector[sector]      # built once per sector, not per symbol
        if symbol in peers:
            subject = peers[symbol]
        elif _uses_market(scope) and symbol in market.peers():
            subject = market.peers()[symbol]        # thin sector: subject rode the fallback
        else:
            subject = _null_subject(sector)
        out[symbol] = engine_score(profile, symbol, subject, cohort, scope).model_dump()
    return out


def _uses_market(scope: dict) -> bool:
    return any(v == "market" for v in scope.values())
