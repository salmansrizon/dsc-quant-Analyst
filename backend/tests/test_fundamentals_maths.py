"""Valuation maths (#59). Pure — no BigQuery, no fixtures beyond numbers.

Several cases here are not hypothetical. AB Bank's ROE and GP's split dividend
are live rows; #58 found them and they are what these guards exist for.
"""
import pytest

from backend import fundamentals as f


# ── metric names ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, expected", [
    ("Return on Equity (ROE)", "ROE"),
    ("Return on Assets (ROA)", "ROA"),
    ("Return on Asset (ROA)", "ROA"),      # sic — non-bank financials
    ("  Current Ratio  ", "CURRENT_RATIO"),
    ("Inventory Turnover", None),          # real, but not a §5 metric
    ("", None),
    (None, None),
])
def test_normalise_metric(name, expected):
    assert f.normalise_metric(name) == expected


def test_both_roa_spellings_collapse_to_one_key():
    # 17 sector-specific codes, two names, one metric (#58). Querying by code
    # cannot join these; the name can.
    assert f.normalise_metric("Return on Assets (ROA)") == f.normalise_metric("Return on Asset (ROA)")


# ── the misleading-ratio guard ───────────────────────────────────────────────

def test_ab_banks_roe_is_flagged_as_misleading():
    """The live row that motivates this: -38.9bn / -32.4bn = 1.1986.

    A loss over negative equity reads as a healthy 120%. Ranked on value alone,
    an insolvent bank sorts to the top of a screener.
    """
    assert f.is_misleading("-38891722887.0000 / -32447856712.0000") is True


def test_an_ordinary_ratio_is_not_flagged():
    assert f.is_misleading("158057490000.0000 / 191322941000.0000") is False


def test_a_plain_loss_is_not_flagged():
    # Negative numerator, positive denominator: -2.95 ROE reads exactly as it
    # should. Nothing to warn about.
    assert f.is_misleading("-19056934828.0000 / 6452566230.0000") is False


@pytest.mark.parametrize("equation", ["", None, "not an equation", "1 / 2 / 3", "a / b"])
def test_an_unparseable_equation_is_not_flagged(equation):
    # Absence of evidence, not evidence of a lie.
    assert f.is_misleading(equation) is False


def test_equation_inputs_parses_a_simple_division():
    assert f.equation_inputs(" 893740267.0000 / 11626518795.0000 ") == (893740267.0, 11626518795.0)


# ── price to book ────────────────────────────────────────────────────────────

def test_price_to_book():
    assert f.price_to_book(257.5, 41.51) == 6.2033


def test_price_to_book_is_none_on_negative_equity():
    # Not "cheap" — meaningless. Returning it would rank an insolvent company
    # as the best value on the exchange.
    assert f.price_to_book(100.0, -32.0) is None


def test_price_to_book_is_none_on_zero_or_missing_nav():
    assert f.price_to_book(100.0, 0) is None
    assert f.price_to_book(100.0, None) is None
    assert f.price_to_book(None, 41.5) is None


# ── dividend yield ───────────────────────────────────────────────────────────

def test_dividend_yield_is_a_percentage_of_face_not_price():
    # 105% of a 10 BDT face = 10.50 BDT per share, on a 257.5 price.
    assert f.dividend_yield(105.0, 257.5) == pytest.approx(4.0777, abs=1e-3)


def test_dividend_yield_uses_the_face_value_the_user_confirmed():
    assert f.FACE_VALUE_BDT == 10.0


def test_dividend_yield_is_none_without_a_dividend_or_price():
    assert f.dividend_yield(None, 257.5) is None
    assert f.dividend_yield(0, 257.5) is None
    assert f.dividend_yield(105.0, None) is None
    assert f.dividend_yield(105.0, 0) is None


def test_an_annual_row_is_the_total_not_another_payment():
    """The trap. The archive lists the year's total AND its instalments:

        GP 2025:     Interim 110 + Final 105       and ANNUAL says 215
        MARICO 2026: 500+600+500+475 = 2075        and ANNUAL says 2075

    Summing every row double-counts — GP's yield came out at 16.7% instead of
    8.3% before this was caught.
    """
    gp = [
        {"year": 2025, "dividend_type": "INTERIM", "cash_dividend_pct": 110.0},
        {"year": 2025, "dividend_type": "ANNUAL", "cash_dividend_pct": 215.0},
        {"year": 2025, "dividend_type": "FINAL", "cash_dividend_pct": 105.0},
    ]
    assert f.annual_cash_dividend(gp, 2025) == 215.0, "the ANNUAL row is the total"

    marico = [
        {"year": 2026, "dividend_type": "ANNUAL", "cash_dividend_pct": 2075.0},
        {"year": 2026, "dividend_type": "FINAL", "cash_dividend_pct": 500.0},
        {"year": 2026, "dividend_type": "INTERIM", "cash_dividend_pct": 600.0},
        {"year": 2026, "dividend_type": "INTERIM", "cash_dividend_pct": 500.0},
        {"year": 2026, "dividend_type": "INTERIM", "cash_dividend_pct": 475.0},
    ]
    assert f.annual_cash_dividend(marico, 2026) == 2075.0


def test_components_are_summed_only_when_the_year_has_no_total():
    # A year still mid-cycle has instalments but no ANNUAL row yet.
    mid_cycle = [
        {"year": 2026, "dividend_type": "INTERIM", "cash_dividend_pct": 105.0},
        {"year": 2026, "dividend_type": "INTERIM", "cash_dividend_pct": 95.0},
    ]
    assert f.annual_cash_dividend(mid_cycle, 2026) == 200.0


def test_the_yield_year_is_the_last_one_that_finished_declaring():
    """GP live: 2026 has only an interim 105% so far; 2025 paid 110% + 105%.

    Reading the newest year with any cash in it halves the yield — 4.1% instead
    of 8.3%. A FINAL or ANNUAL declaration is what marks a year as done.
    """
    declarations = [
        {"year": 2026, "dividend_type": "INTERIM", "cash_dividend_pct": 105.0},
        {"year": 2025, "dividend_type": "FINAL", "cash_dividend_pct": 105.0},
        {"year": 2025, "dividend_type": "INTERIM", "cash_dividend_pct": 110.0},
    ]
    year = f.latest_complete_dividend_year(declarations)
    assert year == 2025, "2026 is still mid-cycle"
    assert f.annual_cash_dividend(declarations, year) == 215.0


def test_a_company_that_only_pays_interims_still_gets_a_year():
    # Understating beats reporting nothing.
    declarations = [
        {"year": 2025, "dividend_type": "INTERIM", "cash_dividend_pct": 50.0},
        {"year": 2024, "dividend_type": "INTERIM", "cash_dividend_pct": 40.0},
    ]
    assert f.latest_complete_dividend_year(declarations) == 2025


def test_a_year_closed_with_no_cash_does_not_win():
    # A stock-only final does not make 2026 the yield year.
    declarations = [
        {"year": 2026, "dividend_type": "FINAL", "cash_dividend_pct": None},
        {"year": 2025, "dividend_type": "ANNUAL", "cash_dividend_pct": 80.0},
    ]
    assert f.latest_complete_dividend_year(declarations) == 2025


def test_no_declarations_means_no_yield_year():
    assert f.latest_complete_dividend_year([]) is None


def test_annual_cash_dividend_is_none_for_a_year_with_no_cash():
    declarations = [{"year": 2025, "cash_dividend_pct": None},
                    {"year": 2025, "cash_dividend_pct": 0}]
    assert f.annual_cash_dividend(declarations, 2025) is None
    assert f.annual_cash_dividend(declarations, 1999) is None


# ── EPS growth and PEG ───────────────────────────────────────────────────────

def test_eps_growth_compares_the_two_most_recent_years():
    # GP: 26.89 (2024) -> 21.90 (2025) is a fall.
    assert f.eps_growth({2023: 24.49, 2024: 26.89, 2025: 21.90}) == pytest.approx(-18.55, abs=0.01)


def test_eps_growth_needs_two_years():
    assert f.eps_growth({2025: 21.9}) is None
    assert f.eps_growth({}) is None


def test_eps_growth_is_none_when_the_earlier_year_was_a_loss():
    # Growth from a loss is not a percentage anyone can read: -200% would sort
    # as terrible for a company that in fact returned to profit.
    assert f.eps_growth({2024: -5.0, 2025: 5.0}) is None
    assert f.eps_growth({2024: 0.0, 2025: 5.0}) is None


def test_eps_growth_ignores_years_with_no_eps():
    assert f.eps_growth({2023: 10.0, 2024: None, 2025: 12.0}) == pytest.approx(20.0)


def test_peg():
    assert f.peg(13.29, 20.0) == pytest.approx(0.6645, abs=1e-3)


@pytest.mark.parametrize("pe, growth", [
    (None, 20.0), (13.0, None),
    (-5.0, 20.0),     # a negative P/E is a loss, not cheapness
    (13.0, -18.55),   # a PEG on shrinking EPS is a sign flip waiting to mislead
    (13.0, 0.0),
])
def test_peg_is_none_unless_both_inputs_are_positive(pe, growth):
    assert f.peg(pe, growth) is None
