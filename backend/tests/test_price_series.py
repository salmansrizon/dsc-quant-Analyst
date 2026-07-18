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


# ── stock_dividend_factor / adjustment_factors (#63) ────────────────────────

def test_stock_dividend_factor_of_50_percent():
    assert ps.stock_dividend_factor(50) == pytest.approx(1 / 1.5)


def test_stock_dividend_factor_of_100_percent_halves():
    assert ps.stock_dividend_factor(100) == pytest.approx(0.5)


def test_adjustment_factors_skips_cash_only_declarations():
    declarations = [
        {"record_date": "2025-12-22", "stock_dividend_pct": None, "cash_dividend_pct": 10},
    ]
    assert ps.adjustment_factors(declarations) == []


def test_adjustment_factors_skips_rows_with_no_record_date():
    declarations = [{"record_date": None, "stock_dividend_pct": 50}]
    assert ps.adjustment_factors(declarations) == []


def test_adjustment_factors_keeps_bonus_declarations():
    declarations = [{"record_date": "2025-12-22", "stock_dividend_pct": 50}]
    assert ps.adjustment_factors(declarations) == [("2025-12-22", pytest.approx(1 / 1.5))]


# ── from_price_history adjustment (#63) ─────────────────────────────────────

def test_no_factors_leaves_prices_unadjusted():
    rows = [_bar(close=10.0, Date="2026-01-02"), _bar(close=5.0, Date="2026-01-01")]
    closes, _, _, _ = ps.from_price_history(rows)
    assert closes == [5.0, 10.0]


def test_bar_on_record_date_is_adjusted_down():
    """EASTRNLUB, 50% bonus, record_date 2025-12-22 (#33): the last cum day
    (2501.5) is scaled down to the continuous pre-bonus-equivalent price, and
    the ex-day bar (already low, real) is left alone.
    """
    rows = [
        _bar(close=1719.9, Date="2025-12-23"),  # ex-day: already reflects the bonus
        _bar(close=2501.5, Date="2025-12-22"),  # last cum day
    ]
    factors = [("2025-12-22", ps.stock_dividend_factor(50))]
    closes, _, _, _ = ps.from_price_history(rows, factors)
    assert closes == [pytest.approx(2501.5 / 1.5), 1719.9]


def test_bars_before_record_date_are_also_adjusted():
    rows = [
        _bar(close=2501.5, Date="2025-12-22"),
        _bar(close=2400.0, Date="2025-12-01"),  # well before the bonus
    ]
    factors = [("2025-12-22", ps.stock_dividend_factor(50))]
    closes, _, _, _ = ps.from_price_history(rows, factors)
    assert closes == [pytest.approx(2400.0 / 1.5), pytest.approx(2501.5 / 1.5)]


def test_high_low_are_scaled_by_the_same_factor():
    rows = [_bar(close=2501.5, high=2600.0, low=2400.0, Date="2025-12-22")]
    factors = [("2025-12-22", ps.stock_dividend_factor(50))]
    closes, highs, lows, _ = ps.from_price_history(rows, factors)
    assert closes == [pytest.approx(2501.5 / 1.5)]
    assert highs == [pytest.approx(2600.0 / 1.5)]
    assert lows == [pytest.approx(2400.0 / 1.5)]


def test_volume_is_never_adjusted():
    rows = [_bar(close=2501.5, volume=1000.0, Date="2025-12-22")]
    factors = [("2025-12-22", ps.stock_dividend_factor(50))]
    _, _, _, volumes = ps.from_price_history(rows, factors)
    assert volumes == [1000.0]


def test_a_bar_with_no_date_is_left_unadjusted():
    rows = [_bar(close=2501.5)]
    factors = [("2025-12-22", ps.stock_dividend_factor(50))]
    closes, _, _, _ = ps.from_price_history(rows, factors)
    assert closes == [2501.5]


def test_two_bonuses_compound():
    """A bar before both bonuses carries the product of both factors."""
    rows = [
        _bar(close=100.0, Date="2026-06-01"),   # after both
        _bar(close=100.0, Date="2026-01-15"),   # between the two record dates
        _bar(close=100.0, Date="2025-12-01"),   # before both
    ]
    factors = [
        ("2025-12-22", ps.stock_dividend_factor(50)),
        ("2026-02-01", ps.stock_dividend_factor(20)),
    ]
    closes, _, _, _ = ps.from_price_history(rows, factors)
    assert closes == [
        pytest.approx(100.0 / 1.5 / 1.2),   # 2025-12-01: both ahead of it
        pytest.approx(100.0 / 1.2),          # 2026-01-15: only the second is ahead
        pytest.approx(100.0),                # 2026-06-01: both already happened
    ]
