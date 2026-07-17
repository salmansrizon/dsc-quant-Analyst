"""Tests for the price-archive → indicator-array coercion.

None of this had a test before it was extracted from
market_service.technical_indicators: it was only reachable through a live
BigQuery query, so the judgement calls that decide whether an indicator is
*right* were the untested half, while the pure maths behind them had 30+ tests.
"""
import pytest

from backend import price_series as ps


def _bar(close=None, high=None, low=None, volume=None, **extra):
    row = {"Close": close, "High": high, "Low": low, "Volume": volume}
    row.update(extra)
    return row


# ── to_number ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    (1.5, 1.5), ("1.5", 1.5), (2, 2.0), ("-3.25", -3.25), (0, 0.0),
    (None, None), ("", None), ("-", None), ("n/a", None), ([], None),
])
def test_to_number(raw, expected):
    assert ps.to_number(raw) == expected


def test_zero_is_a_number_not_a_missing_value():
    # `if not value` would swallow this; a 0.0 close is a real (if odd) datum.
    assert ps.to_number(0) == 0.0
    assert ps.to_number("0.0") == 0.0


# ── column ───────────────────────────────────────────────────────────────────

def test_column_takes_the_first_key_that_parses():
    rows = [{"Close": 10.0, "LTP": 99.0}]
    assert ps.column(rows, "Close", "LTP") == [10.0]


def test_column_falls_back_when_the_first_key_is_missing():
    rows = [{"LTP": 99.0}]
    assert ps.column(rows, "Close", "LTP") == [99.0]


def test_column_falls_back_when_the_first_key_is_unparseable():
    # The archive writes '-' for a missing close, not NULL.
    rows = [{"Close": "-", "LTP": 99.0}]
    assert ps.column(rows, "Close", "LTP") == [99.0]


def test_column_is_none_when_no_key_parses():
    assert ps.column([{"Close": "-", "LTP": None}], "Close", "LTP") == [None]


# ── from_price_history ───────────────────────────────────────────────────────

def test_rows_are_reversed_into_oldest_first():
    """price_history returns newest-first. Every indicator assumes the
    opposite, and getting it backwards silently inverts every trend.
    """
    newest_first = [_bar(close=3.0), _bar(close=2.0), _bar(close=1.0)]
    closes, _, _, _ = ps.from_price_history(newest_first)
    assert closes == [1.0, 2.0, 3.0]


def test_close_is_preferred_over_ltp():
    closes, _, _, _ = ps.from_price_history([_bar(close=10.0, LTP=99.0)])
    assert closes == [10.0]


def test_ltp_stands_in_when_close_is_absent():
    closes, _, _, _ = ps.from_price_history([_bar(close=None, LTP=99.0)])
    assert closes == [99.0]


def test_a_row_with_no_usable_close_is_dropped_with_its_whole_bar():
    # The four arrays must stay index-aligned — every indicator zips them.
    rows = [
        _bar(close=1.0, high=1.5, low=0.5, volume=100),
        _bar(close=None, high=9.9, low=9.9, volume=999),   # unusable
        _bar(close=3.0, high=3.5, low=2.5, volume=300),
    ]
    closes, highs, lows, volumes = ps.from_price_history(rows)

    assert closes == [3.0, 1.0]        # reversed, and the bad bar is gone
    assert highs == [3.5, 1.5]
    assert lows == [2.5, 0.5]
    assert volumes == [300.0, 100.0]
    assert len(closes) == len(highs) == len(lows) == len(volumes)


def test_dropping_a_row_collapses_a_calendar_gap():
    """The distortion v1 accepts (#31), pinned so it is a decision not a
    surprise: a missing bar makes its neighbours adjacent, so a 20-day SMA can
    span 21 calendar days.
    """
    rows = [
        _bar(close=3.0, Date="2026-01-03"),
        _bar(close=None, Date="2026-01-02"),   # a holiday, say
        _bar(close=1.0, Date="2026-01-01"),
    ]
    closes, _, _, _ = ps.from_price_history(rows)
    assert closes == [1.0, 3.0], "Jan 1 and Jan 3 are now neighbours"


def test_high_and_low_fall_back_to_the_close():
    # A bar with no range, rather than a bar with a None in it.
    closes, highs, lows, _ = ps.from_price_history([_bar(close=5.0, high=None, low=None)])
    assert (closes, highs, lows) == ([5.0], [5.0], [5.0])


def test_volume_falls_back_to_zero_not_the_close():
    # OBV and VWAP read this as "no trade". Falling back to the close would
    # invent turnover.
    _, _, _, volumes = ps.from_price_history([_bar(close=5.0, volume=None)])
    assert volumes == [0.0]


def test_no_rows_yields_four_empty_arrays():
    assert ps.from_price_history([]) == ([], [], [], [])


def test_rows_with_no_usable_close_at_all_yield_empty_arrays():
    # technical_indicators reports points=0 off the back of this.
    assert ps.from_price_history([_bar(close=None), _bar(close="-")]) == ([], [], [], [])


def test_strings_from_the_archive_are_coerced():
    # BigQuery hands back strings for some archive columns.
    rows = [_bar(close="1.5", high="2.0", low="1.0", volume="100")]
    assert ps.from_price_history(rows) == ([1.5], [2.0], [1.0], [100.0])


def test_the_caller_is_not_mutated():
    rows = [_bar(close=1.0), _bar(close=2.0)]
    before = [dict(r) for r in rows]
    ps.from_price_history(rows)
    assert rows == before, "reversed() must not reorder the caller's list"
