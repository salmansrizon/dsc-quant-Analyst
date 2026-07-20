"""Wires the pure fit engine (#88) to BigQuery: builds a stock's metrics and its
sector cohort, then hands both to `fit_engine.score`.

The cohort is built by BULK queries per sector — four aggregate reads, never a
per-symbol fan-out of `get_fundamentals` (that would be N×several queries a
scorecard). Every peer's metric is derived in Python by the SAME `valuation`
functions the single-stock path uses, so the subject is compared like-for-like
against its peers.
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


def _sector_of(symbol: str) -> str | None:
    rows = db.query_rows(
        f"SELECT Sector FROM {db.table_id('lankabd_datamatrix')} WHERE Symbol = @s LIMIT 1",
        [bigquery.ScalarQueryParameter("s", "STRING", symbol)],
    )
    return rows[0]["Sector"] if rows else None


def _peer_metrics(sector: str) -> dict[str, dict]:
    """Every symbol in `sector`, each with its derived fit metrics — the same
    figures `get_fundamentals` computes, but for the whole cohort in four reads."""
    p = [bigquery.ScalarQueryParameter("sector", "STRING", sector)]
    dm = db.query_rows(
        f"""SELECT Symbol, LTP, Forward_PE, Audited_PE
            FROM {db.table_id('lankabd_datamatrix')} WHERE Sector = @sector""", p)
    earn = db.query_rows(
        f"""SELECT symbol, year, eps, nav FROM {db.current_view('fundamentals_earnings')}
            WHERE sector = @sector AND period = 'ANNUAL'""", p)
    divs = db.query_rows(
        f"""SELECT symbol, year, dividend_type, cash_dividend_pct, publish_date
            FROM {db.current_view('fundamentals_dividends')} WHERE sector = @sector""", p)
    vol = db.query_rows(
        f"""SELECT Symbol, SAFE_DIVIDE(STDDEV(Close), AVG(Close)) AS vol FROM (
              SELECT Symbol, Close, ROW_NUMBER() OVER (
                PARTITION BY Symbol ORDER BY Date DESC) AS rn
              FROM {db.table_id('lankabd_price_archive')} WHERE Sector = @sector
            ) WHERE rn <= {_VOL_BARS}
            GROUP BY Symbol HAVING COUNT(*) >= {_VOL_MIN}""", p)

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
    vol_by_symbol = {r["Symbol"]: r["vol"] for r in vol if r.get("vol") is not None}

    out: dict[str, dict] = {}
    for r in dm:
        sym = r["Symbol"]
        price = r.get("LTP")
        pe = r.get("Forward_PE") or r.get("Audited_PE")
        nav = nav_by_symbol.get(sym, (None, None))[1]
        decls = decls_by_symbol.get(sym, [])
        div_year = valuation.latest_complete_dividend_year(decls)
        cash = valuation.annual_cash_dividend(decls, div_year) if div_year else None
        out[sym] = {
            "sector": sector,
            "pe": pe if (pe and pe > 0) else None,
            "pb": valuation.price_to_book(price, nav),
            "yield_": valuation.dividend_yield(cash, price),
            "growth": valuation.eps_growth(eps_by_symbol.get(sym, {})),
            "volatility": vol_by_symbol.get(sym),
        }
    return out


def _cohort_arrays(peers: dict[str, dict]) -> dict[str, list[float]]:
    keys = {"pe": "pe", "pb": "pb", "yield": "yield_", "growth": "growth",
            "volatility": "volatility"}
    return {
        cohort_key: [m[subj_key] for m in peers.values() if m.get(subj_key) is not None]
        for cohort_key, subj_key in keys.items()
    }


def fit_for(user_id: str, symbol: str) -> dict:
    """The scorecard for one stock against one user's profile."""
    symbol = symbol.upper()
    profile = get_profile(user_id)
    sector = _sector_of(symbol)
    peers = _peer_metrics(sector) if sector else {}
    subject = peers.get(symbol) or {
        "sector": sector, "pe": None, "pb": None, "yield_": None,
        "growth": None, "volatility": None,
    }
    return engine_score(profile, symbol, subject, _cohort_arrays(peers)).model_dump()
