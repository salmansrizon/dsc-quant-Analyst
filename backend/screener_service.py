"""Stock screener: hybrid bulk read + whitelist filters + code-constant presets (#71, from #37).

**Hybrid bulk read (decision 2).** ONE query joins lankabd_datamatrix with each
symbol's latest lankabd_price_archive row (for P/E, market cap) and latest
ANNUAL fundamentals_earnings row (for NAV) — a window function per join, not a
per-symbol fan-out, so all ~414 symbols cost one query each. Native filters
(price/volume/market_cap/pe/sector) push into that query's SQL WHERE.

Dividend yield needs a second bulk query (all symbols, one round trip) because
"which year is complete, which declaration is the year's total" is
valuation.py's job (latest_complete_dividend_year / annual_cash_dividend,
#59) — grouping the flat declaration rows by symbol in Python and calling
those functions reuses that logic exactly, rather than reimplementing it as
SQL, which is what this ticket explicitly rules out.

**P/B and dividend_yield are DERIVED**: computed per row in Python via
valuation.py, and filtered in Python after the bulk read — never in SQL.

**Whitelist filters (decision 3).** FILTER_WHITELIST is a fixed {field:
allowed-operators} map. Every value is bound as a query parameter (native
fields) or compared in Python (derived fields) — never string-interpolated.
An unknown field or an operator that field disallows raises InvalidFilter,
which the API layer turns into a 400.

**Presets (decision 4)** are plain Python dicts, not a `screener_presets`
table — a preset just seeds the same filter list a caller could type by hand.
"""
from google.cloud import bigquery

from . import db
from . import valuation


class InvalidFilter(ValueError):
    """A filter names an unknown field, or an operator that field disallows."""


NUMERIC_OPS = frozenset({"gt", "gte", "lt", "lte", "eq"})
SECTOR_OPS = frozenset({"eq"})

# field -> allowed operators. The whitelist itself: anything not a key here is
# an unknown field, full stop.
FILTER_WHITELIST = {
    "price": NUMERIC_OPS,
    "volume": NUMERIC_OPS,
    "market_cap": NUMERIC_OPS,
    "pe": NUMERIC_OPS,
    "pb": NUMERIC_OPS,
    "dividend_yield": NUMERIC_OPS,
    "sector": SECTOR_OPS,
}

# Native fields resolve to a column in the bulk-read SQL and push into WHERE.
# Fields in FILTER_WHITELIST but not here (pb, dividend_yield) are derived —
# see DERIVED_FIELDS — and can only be filtered after the Python compute step.
_NATIVE_SQL_COLUMN = {
    "price": "d.LTP",
    "volume": "d.Volume_Qty_",
    "market_cap": "p.Market_Cap__BDT_bn_",
    "pe": "COALESCE(p.Forward_PE, p.Audited_PE)",
    "sector": "d.Sector",
}
NATIVE_FIELDS = frozenset(_NATIVE_SQL_COLUMN)
DERIVED_FIELDS = frozenset({"pb", "dividend_yield"})

_SQL_OP = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "="}

_PY_OP = {
    "gt": lambda a, b: a is not None and a > b,
    "gte": lambda a, b: a is not None and a >= b,
    "lt": lambda a, b: a is not None and a < b,
    "lte": lambda a, b: a is not None and a <= b,
    "eq": lambda a, b: a is not None and a == b,
}

# Presets as code constants (decision 4) — three shipped in v1. Values are a
# starting point, not a spec'd definition; the technical presets (Momentum,
# Oversold, Overbought, Breakout) need the v2 signal snapshot (#55) and are
# out of scope here.
PRESETS = {
    "value": [
        {"field": "pe", "op": "gt", "value": 0},
        {"field": "pe", "op": "lte", "value": 15},
        {"field": "pb", "op": "gt", "value": 0},
        {"field": "pb", "op": "lte", "value": 1.5},
    ],
    "growth": [
        {"field": "pe", "op": "gt", "value": 25},
    ],
    "dividend_kings": [
        {"field": "dividend_yield", "op": "gte", "value": 5},
    ],
}


def resolve_filters(preset: str | None, filters: list[dict] | None) -> list[dict]:
    """The effective filter list: the named preset's filters, then any
    caller-supplied filters layered on top of it.

    An unknown preset name is the same class of mistake as an unknown field —
    a 400 via InvalidFilter, not a silent "no preset applied".
    """
    effective: list[dict] = []
    if preset is not None:
        if preset not in PRESETS:
            raise InvalidFilter(f"Unknown preset: {preset!r}")
        effective.extend(PRESETS[preset])
    if filters:
        effective.extend(filters)
    return effective


def _validate(filters: list[dict]) -> None:
    for f in filters:
        field, op = f.get("field"), f.get("op")
        allowed = FILTER_WHITELIST.get(field)
        if allowed is None:
            raise InvalidFilter(f"Unknown filter field: {field!r}")
        if op not in allowed:
            raise InvalidFilter(f"Operator {op!r} is not allowed for field {field!r}")


def _native_where(filters: list[dict]) -> tuple[str, list]:
    """SQL WHERE text (bound params only) plus the ScalarQueryParameters it
    references. Derived-field filters (pb, dividend_yield) are skipped here —
    they are applied in Python, after the bulk read.
    """
    clauses, params = [], []
    for i, f in enumerate(filters):
        if f["field"] not in NATIVE_FIELDS:
            continue
        column = _NATIVE_SQL_COLUMN[f["field"]]
        name = f"nf{i}"
        param_type = "STRING" if f["field"] == "sector" else "FLOAT64"
        clauses.append(f"{column} {_SQL_OP[f['op']]} @{name}")
        params.append(bigquery.ScalarQueryParameter(name, param_type, f["value"]))
    return (" AND ".join(clauses) if clauses else "TRUE"), params


def _bulk_rows(where_sql: str, params: list) -> list[dict]:
    """The hybrid bulk read (decision 2): one query, all symbols.

    latest_price and latest_earnings are windowed, not correlated subqueries —
    BigQuery rejects a correlated subquery inside a JOIN predicate (the same
    constraint fundamentals_service._latest_price works around per-symbol);
    windowing it once for every symbol is the bulk-read shape this ticket asks
    for instead.
    """
    sql = f"""
        WITH latest_price AS (
          SELECT Symbol, Forward_PE, Audited_PE, Market_Cap__BDT_bn_,
                 ROW_NUMBER() OVER (PARTITION BY Symbol ORDER BY Date DESC) AS _rn
          FROM {db.table_id('lankabd_price_archive')}
        ),
        latest_earnings AS (
          SELECT symbol, nav,
                 ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY year DESC) AS _rn
          FROM {db.current_view('fundamentals_earnings')}
          WHERE period = 'ANNUAL'
        )
        SELECT d.Symbol AS symbol, d.Sector AS sector,
               d.LTP AS price, d.Volume_Qty_ AS volume,
               COALESCE(p.Forward_PE, p.Audited_PE) AS pe,
               p.Market_Cap__BDT_bn_ AS market_cap,
               e.nav AS nav
        FROM {db.table_id('lankabd_datamatrix')} d
        LEFT JOIN latest_price p ON p.Symbol = d.Symbol AND p._rn = 1
        LEFT JOIN latest_earnings e ON e.symbol = d.Symbol AND e._rn = 1
        WHERE {where_sql}
    """
    return db.query_rows(sql, params)


def _cash_dividend_pcts() -> dict:
    """symbol -> latest complete year's annual cash dividend %, or None.

    One query for every symbol's declarations, then valuation.py's exact
    per-symbol selection logic (#59) grouped in Python — see the module
    docstring for why this cannot be pushed into SQL.
    """
    rows = db.query_rows(f"""
        SELECT symbol, year, dividend_type, cash_dividend_pct, publish_date
        FROM {db.current_view('fundamentals_dividends')}
    """)
    by_symbol: dict[str, list[dict]] = {}
    for r in rows:
        by_symbol.setdefault(r["symbol"], []).append(r)

    out = {}
    for symbol, declarations in by_symbol.items():
        year = valuation.latest_complete_dividend_year(declarations)
        out[symbol] = valuation.annual_cash_dividend(declarations, year) if year else None
    return out


def _with_derived(rows: list[dict], cash_pcts: dict) -> list[dict]:
    """Attach pb/dividend_yield, computed via valuation.py, to each bulk row."""
    out = []
    for r in rows:
        price = r.get("price")
        out.append({
            "symbol": r["symbol"],
            "sector": r.get("sector"),
            "price": price,
            "volume": r.get("volume"),
            "market_cap": r.get("market_cap"),
            "pe": r.get("pe"),
            "pb": valuation.price_to_book(price, r.get("nav")),
            "dividend_yield": valuation.dividend_yield(cash_pcts.get(r["symbol"]), price),
        })
    return out


def _apply_derived_filters(rows: list[dict], filters: list[dict]) -> list[dict]:
    derived = [f for f in filters if f["field"] in DERIVED_FIELDS]
    if not derived:
        return rows
    return [r for r in rows if all(_PY_OP[f["op"]](r.get(f["field"]), f["value"]) for f in derived)]


def screen(preset: str | None = None, filters: list[dict] | None = None, limit: int = 500) -> list[dict]:
    """Run the screener end to end: resolve preset+filters, whitelist-validate,
    bulk-read with native filters in SQL, then derived filters in Python.

    Raises InvalidFilter for an unknown preset/field/operator — the API layer
    maps that to 400.
    """
    effective = resolve_filters(preset, filters)
    _validate(effective)

    where_sql, params = _native_where(effective)
    rows = _bulk_rows(where_sql, params)
    cash_pcts = _cash_dividend_pcts()

    results = _with_derived(rows, cash_pcts)
    results = _apply_derived_filters(results, effective)
    results.sort(key=lambda r: r["symbol"])
    return results[: int(limit)]
