"""Assemble one company's fundamentals for the API (#59).

Reads the four fundamentals tables plus the price archive, and hands the pure
maths in fundamentals.py the numbers it needs. Mirrors
market_service.technical_indicators (#31): the query lives here, the arithmetic
lives behind a seam with no BigQuery import.
"""
from google.cloud import bigquery

from . import db
from . import fundamentals


def _reported(symbol: str, limit: int = 12) -> list[dict]:
    """Annual EPS/NAV history, newest first. The archive reaches back to 2014."""
    return db.query_rows(
        f"""
        SELECT year, period, eps, nav, publish_date, source
        FROM {db.current_view('fundamentals_earnings')}
        WHERE symbol = @symbol AND period = 'ANNUAL'
        ORDER BY year DESC
        LIMIT {int(limit)}
        """,
        [bigquery.ScalarQueryParameter("symbol", "STRING", symbol)],
    )


def _dividends(symbol: str, limit: int = 40) -> list[dict]:
    """Every dividend declaration, newest first. Several per year is normal."""
    return db.query_rows(
        f"""
        SELECT year, dividend_type, cash_dividend_pct, stock_dividend_pct, publish_date
        FROM {db.current_view('fundamentals_dividends')}
        WHERE symbol = @symbol
        ORDER BY year DESC, publish_date DESC
        LIMIT {int(limit)}
        """,
        [bigquery.ScalarQueryParameter("symbol", "STRING", symbol)],
    )


def _ratios(symbol: str) -> list[dict]:
    """Reported ratios for the latest year the company has any."""
    return db.query_rows(
        f"""
        SELECT year, code, name, category, result, equation
        FROM {db.current_view('fundamentals_ratios')}
        WHERE symbol = @symbol
          AND year = (
            SELECT MAX(year) FROM {db.current_view('fundamentals_ratios')}
            WHERE symbol = @symbol
          )
        """,
        [bigquery.ScalarQueryParameter("symbol", "STRING", symbol)],
    )


def _latest_price(symbol: str) -> dict:
    """LTP, P/E and market cap. The datamatrix has the live price; the archive
    carries the valuation columns lankabd computes daily.
    """
    # The archive's latest bar is picked in a subquery in the FROM, not in the
    # JOIN predicate — BigQuery rejects a correlated subquery there
    # ("Unsupported subquery with table in join predicate").
    rows = db.query_rows(
        f"""
        SELECT d.LTP AS price, a.Forward_PE AS forward_pe,
               a.Audited_PE AS audited_pe, a.Market_Cap__BDT_bn_ AS market_cap_bdt_bn,
               a.Date AS priced_on
        FROM {db.table_id('lankabd_datamatrix')} d
        LEFT JOIN (
          SELECT Symbol, Forward_PE, Audited_PE, Market_Cap__BDT_bn_, Date,
                 ROW_NUMBER() OVER (PARTITION BY Symbol ORDER BY Date DESC) AS _rn
          FROM {db.table_id('lankabd_price_archive')}
          WHERE Symbol = @symbol
        ) a ON a.Symbol = d.Symbol AND a._rn = 1
        WHERE d.Symbol = @symbol
        LIMIT 1
        """,
        [bigquery.ScalarQueryParameter("symbol", "STRING", symbol)],
    )
    return rows[0] if rows else {}


def _reported_metrics(ratios: list[dict]) -> dict:
    """The spec-§5 ratios, keyed by a stable metric name.

    Each carries `misleading` — see fundamentals.is_misleading. AB Bank's ROE
    reads as a healthy 120% because it is a loss over negative equity, and a
    consumer that ranks on `value` alone will put it first.
    """
    out = {}
    for r in ratios:
        key = fundamentals.normalise_metric(r["name"])
        if not key:
            continue
        out[key] = {
            "value": r["result"],
            "reported_as": r["name"],
            "category": r["category"],
            "year": r["year"],
            "equation": r["equation"],
            "misleading": fundamentals.is_misleading(r["equation"]),
        }
    return out


def get_fundamentals(symbol: str) -> dict:
    """Everything spec §5 asks for, for one symbol.

    `reported` comes from the company API as-is. `derived` is computed here on
    read (#31's decision) because it all depends on a live price. A derived
    figure is None when the inputs make it meaningless rather than merely
    absent — see fundamentals.py.
    """
    symbol = symbol.upper()
    reported_years = _reported(symbol)
    declarations = _dividends(symbol)
    ratios = _ratios(symbol)
    price_row = _latest_price(symbol)

    if not reported_years and not ratios and not price_row:
        return {}

    price = price_row.get("price")
    latest = reported_years[0] if reported_years else {}
    nav = latest.get("nav")
    pe = price_row.get("forward_pe") or price_row.get("audited_pe")

    eps_by_year = {r["year"]: r["eps"] for r in reported_years if r.get("eps") is not None}
    growth = fundamentals.eps_growth(eps_by_year)

    # Yield reads off the latest year that has FINISHED declaring — the current
    # year is usually mid-cycle, and taking it would halve the number.
    dividend_year = fundamentals.latest_complete_dividend_year(declarations)
    cash_pct = fundamentals.annual_cash_dividend(declarations, dividend_year) if dividend_year else None

    return {
        "symbol": symbol,
        "price": price,
        "market_cap_bdt_bn": price_row.get("market_cap_bdt_bn"),
        "pe": pe,
        "reported": _reported_metrics(ratios),
        "derived": {
            "price_to_book": fundamentals.price_to_book(price, nav),
            "dividend_yield_pct": fundamentals.dividend_yield(cash_pct, price),
            "dividend_year": dividend_year,
            "cash_dividend_pct": cash_pct,
            "eps_growth_pct": growth,
            "peg": fundamentals.peg(pe, growth),
        },
        "latest_annual": {
            "year": latest.get("year"),
            "eps": latest.get("eps"),
            "nav": nav,
        },
        "eps_history": [
            {"year": r["year"], "eps": r["eps"], "nav": r["nav"]} for r in reported_years
        ],
        "dividends": declarations,
        "caveats": [fundamentals.MUTUAL_FUND_CAVEAT] if cash_pct else [],
    }
