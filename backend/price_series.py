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


def from_price_history(rows: list[dict]) -> tuple[list, list, list, list]:
    """(closes, highs, lows, volumes), oldest-first, aligned and gap-free.

    Rows arrive newest-first from price_history and are reversed here.

    A row with no usable close is dropped, taking its high/low/volume with it —
    the four arrays stay index-aligned, which every indicator assumes. **This
    collapses calendar gaps into adjacent bars**: a missing Wednesday makes
    Tuesday and Thursday neighbours, and a 20-day SMA spans 21 calendar days.
    v1 accepts the distortion (#31); it is recorded here rather than in a
    comment inside a function nothing can call.

    High/low fall back to the close when absent — a bar with no range. Volume
    falls back to 0.0, which OBV and VWAP treat as "no trade", not "unknown".
    """
    rows = list(reversed(rows))

    closes = column(rows, *CLOSE_KEYS)
    highs = column(rows, *HIGH_KEYS)
    lows = column(rows, *LOW_KEYS)
    volumes = column(rows, *VOLUME_KEYS)

    usable = [
        (c, h, l, v)
        for c, h, l, v in zip(closes, highs, lows, volumes)
        if c is not None
    ]
    if not usable:
        return [], [], [], []

    return (
        [c for c, _, _, _ in usable],
        [h if h is not None else c for c, h, _, _ in usable],
        [l if l is not None else c for c, _, l, _ in usable],
        [v if v is not None else 0.0 for *_, v in usable],
    )
