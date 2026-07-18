"""Turn price-archive rows into the parallel arrays indicators.py wants.

Pure: rows in, arrays out, no BigQuery import. That is the point — this is the
code that decides whether an indicator is *right*, and until it was extracted it
lived inside market_service.technical_indicators, reachable only through a live
query and therefore untested.

indicators.py (#31) got the seam and 30+ tests for the maths. The judgement
calls were all on this side of it:

  - the archive returns newest-first; every indicator needs oldest-first
  - `Close` is authoritative but sometimes absent, so `LTP` stands in
  - a row with no usable close cannot be charted, and dropping it silently
    collapses a calendar gap into an adjacent bar
"""
from typing import Iterable

# Columns are tried in order; the first that parses wins. price_history aliases
# OPENP_ to Open and Volume_Qty_ to Volume, so these are the names it returns.
CLOSE_KEYS = ("Close", "LTP")
HIGH_KEYS = ("High",)
LOW_KEYS = ("Low",)
VOLUME_KEYS = ("Volume",)


def to_number(value) -> float | None:
    """A float, or None. The archive holds '-', '', and stray strings."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def column(rows: Iterable[dict], *keys: str) -> list[float | None]:
    """One column, taking the first key that yields a number for each row."""
    out = []
    for row in rows:
        value = None
        for key in keys:
            value = to_number(row.get(key))
            if value is not None:
                break
        out.append(value)
    return out


def stock_dividend_factor(pct: float) -> float:
    """The price factor a bonus/stock-dividend of `pct`% dilutes to: `1/(1+pct/100)`.

    A 50% bonus -> 0.6667; a 100% bonus -> 0.5. Same shape covers a face-value
    split `N:1` as `1/N`, but no split source is ingested yet (#33) so only
    bonus declarations feed `adjustment_factors` today.
    """
    return 1.0 / (1.0 + pct / 100.0)


def adjustment_factors(declarations: Iterable[dict]) -> list[tuple]:
    """(record_date, factor) for every bonus/stock-dividend declaration.

    Cash-only declarations (no `stock_dividend_pct`) and rows with no
    `record_date` are not price adjustments and are skipped (#63 scope: bonus/
    split price adjustment only — cash dividends are a total-return convention,
    deferred to v2).
    """
    return [
        (d["record_date"], stock_dividend_factor(d["stock_dividend_pct"]))
        for d in declarations
        if d.get("stock_dividend_pct") and d.get("record_date")
    ]


def _cumulative_factor(date, factors: list[tuple]) -> float:
    """Product of every factor whose action is still ahead of this bar.

    lankabd gives record_date, not ex-date; #33 confirmed against EASTRNLUB's
    50% bonus that record_date is the **last cum-dividend day** — a bar dated
    on or before it is still at the pre-bonus price and must be scaled down.
    `date <= record_date` is therefore the adjust-this-bar test, not `<`.
    """
    result = 1.0
    for record_date, factor in factors:
        if date <= record_date:
            result *= factor
    return result


def dedupe_by_date(rows: list[dict]) -> list[dict]:
    """Drop rows that repeat a Date, keeping the first (#64).

    `lankabd_price_archive` holds every (Symbol, Date) twice; a query is
    per-symbol, so a repeated Date is a duplicate bar. Left in, every indicator
    double-counts every day. Rows with no Date are kept — they cannot be proven
    duplicates.
    """
    seen = set()
    out = []
    for row in rows:
        date = row.get("Date")
        if date is not None and date in seen:
            continue
        if date is not None:
            seen.add(date)
        out.append(row)
    return out


def from_price_history(rows: list[dict], factors: Iterable[tuple] | None = None) -> tuple[list, list, list, list]:
    """(closes, highs, lows, volumes), oldest-first, aligned, gap-free, adjusted.

    Rows arrive newest-first from price_history and are reversed here.

    A row with no usable close is dropped, taking its high/low/volume with it —
    the four arrays stay index-aligned, which every indicator assumes. **This
    collapses calendar gaps into adjacent bars**: a missing Wednesday makes
    Tuesday and Thursday neighbours, and a 20-day SMA spans 21 calendar days.
    v1 accepts the distortion (#31); it is recorded here rather than in a
    comment inside a function nothing can call.

    High/low fall back to the close when absent — a bar with no range. Volume
    falls back to 0.0, which OBV and VWAP treat as "no trade", not "unknown".

    `factors` (see `adjustment_factors`, #63) is an on-read corporate-action
    adjustment: closes/highs/lows are scaled by the cumulative bonus/split
    factor before indicators.py ever sees them, so it never learns adjustment
    exists. Volume is never scaled. Rows with no `Date` are left unadjusted —
    there is nothing to compare a record_date against.

    Duplicate-Date rows are collapsed and non-positive closes dropped (#64): the
    archive stores every bar twice and carries stray 0.0 closes, both of which
    corrupt every indicator (a double-counted bar, and a real -100% crash plus a
    near-zero division). A non-positive close is dropped exactly as a missing one
    is — the same accepted gap-collapse.
    """
    rows = dedupe_by_date(list(reversed(rows)))

    closes = column(rows, *CLOSE_KEYS)
    highs = column(rows, *HIGH_KEYS)
    lows = column(rows, *LOW_KEYS)
    volumes = column(rows, *VOLUME_KEYS)

    usable = [
        (c, h, l, v, row.get("Date"))
        for row, c, h, l, v in zip(rows, closes, highs, lows, volumes)
        if c is not None and c > 0
    ]
    if not usable:
        return [], [], [], []

    factors = list(factors) if factors else []

    out_closes, out_highs, out_lows, out_volumes = [], [], [], []
    for c, h, l, v, date in usable:
        h = h if h is not None else c
        l = l if l is not None else c
        v = v if v is not None else 0.0
        f = _cumulative_factor(date, factors) if factors and date is not None else 1.0
        out_closes.append(c * f)
        out_highs.append(h * f)
        out_lows.append(l * f)
        out_volumes.append(v)

    return out_closes, out_highs, out_lows, out_volumes
