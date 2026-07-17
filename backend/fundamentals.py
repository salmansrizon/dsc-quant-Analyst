"""Valuation maths over reported fundamentals (#59).

Pure: numbers in, numbers out, no BigQuery import — the same shape as
indicators.py (#31), and for the same reason. These are computed on read, not
stored: they all depend on a live price, and a stored copy would need its own
refresh path to go stale in.

ROE and ROA are NOT here. They come from the company API already computed
(#58) — deriving them from EPS/NAV would be a second, worse answer.
"""
from typing import Iterable

# A BD share's face value. Dividends are declared as a percentage OF face value,
# not of price: "105%" on a 10 BDT face is 10.50 BDT per share. Confirmed with
# the user 2026-07-17. Mutual funds may differ — see MUTUAL_FUND_CAVEAT.
FACE_VALUE_BDT = 10.0

MUTUAL_FUND_CAVEAT = (
    "Face value is assumed to be 10 BDT for every symbol. Mutual funds may "
    "differ; a yield shown for one is unverified."
)

# The same metric arrives under more than one name because lankabd's ratio
# vocabulary is per sector (#58). Codes are worse — ROA has 17 of them. Only
# variants observed live are listed; the raw name always survives alongside.
METRIC_ALIASES = {
    "Return on Equity (ROE)": "ROE",
    "Return on Assets (ROA)": "ROA",
    "Return on Asset (ROA)": "ROA",        # sic — non-bank financials
    "Net Profit Margin": "NET_MARGIN",
    "Operating Profit Margin": "OPERATING_MARGIN",
    "Gross Profit Margin": "GROSS_MARGIN",
    "EBITDA Margin": "EBITDA_MARGIN",
    "Current Ratio": "CURRENT_RATIO",
    "Debt to Equity": "DEBT_TO_EQUITY",
}


def normalise_metric(name: str) -> str | None:
    """A stable metric key, or None for a ratio #59 does not surface."""
    return METRIC_ALIASES.get((name or "").strip())


def equation_inputs(equation: str) -> tuple[float, float] | None:
    """The (numerator, denominator) a ratio was computed from, if it is a
    simple division. None when it is anything else.

    lankabd ships the arithmetic behind every ratio ("158057490000.0000 /
    191322941000.0000"), which is the only way to see whether the result means
    what it appears to.
    """
    if not equation or "/" not in equation:
        return None
    parts = equation.split("/")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return None


def is_misleading(equation: str) -> bool:
    """Whether a ratio's sign lies about its meaning.

    **AB Bank's 2025 ROE is 1.1986** — a healthy-looking 120%. Its equation is
    `-38,891,722,887 / -32,447,856,712`: a loss over *negative equity*. The bank
    is insolvent and two negatives make it look excellent. Its 2024 ROE, on
    positive equity, is -2.95.

    A negative denominator inverts the sign of the whole ratio, so the number
    cannot be read or ranked at face value. Screening and scoring must exclude
    these rather than sort them to the top.
    """
    inputs = equation_inputs(equation)
    if inputs is None:
        return False
    _, denominator = inputs
    return denominator < 0


def price_to_book(price: float | None, nav: float | None) -> float | None:
    """Price over book value per share. None when NAV is absent or <= 0.

    A negative NAV is negative equity: the multiple is meaningless rather than
    cheap, and returning it would rank an insolvent company as the best value
    on the exchange.
    """
    if price is None or nav is None or nav <= 0:
        return None
    return round(price / nav, 4)


def dividend_yield(cash_dividend_pct: float | None, price: float | None,
                   face_value: float = FACE_VALUE_BDT) -> float | None:
    """Annual cash dividend over price, as a percentage.

    `cash_dividend_pct` is a percentage of FACE VALUE, not of price: 105% on a
    10 BDT face pays 10.50 BDT per share. Sum a year's declarations before
    calling — GP 2025 paid an interim 110% and a final 105%.
    """
    if not cash_dividend_pct or not price or price <= 0:
        return None
    per_share = (cash_dividend_pct / 100.0) * face_value
    return round((per_share / price) * 100.0, 4)


def eps_growth(eps_by_year: dict[int, float]) -> float | None:
    """Year-on-year EPS growth between the two most recent years, as a
    percentage. None when there is no comparable pair.

    Returns None when the earlier EPS is <= 0: growth from a loss is not a
    percentage anyone can read, and -200% would sort as terrible when the
    company in fact returned to profit.
    """
    years = sorted(y for y, e in eps_by_year.items() if e is not None)
    if len(years) < 2:
        return None
    latest, previous = eps_by_year[years[-1]], eps_by_year[years[-2]]
    if previous is None or previous <= 0 or latest is None:
        return None
    return round(((latest - previous) / previous) * 100.0, 4)


def peg(pe: float | None, growth_pct: float | None) -> float | None:
    """P/E over EPS growth. None unless both are positive.

    A PEG built on negative growth or a negative P/E is not a cheapness signal;
    it is a sign flip waiting to mislead a screener.
    """
    if pe is None or growth_pct is None or pe <= 0 or growth_pct <= 0:
        return None
    return round(pe / growth_pct, 4)


# A year is done paying once it declares one of these. An INTERIM alone means
# more is still to come.
YEAR_CLOSING_DECLARATIONS = frozenset({"ANNUAL", "FINAL"})


def latest_complete_dividend_year(declarations: Iterable[dict]) -> int | None:
    """The most recent year that has finished declaring, or None.

    Yield must not be read off a year still in progress. GP is the case: 2026
    has only an interim 105% so far, while 2025 paid 110% + 105% = 215%. Taking
    the newest year with any cash in it halves the yield.

    A year counts as finished once it declares ANNUAL or FINAL. If no year has
    (a company that only ever pays interims), fall back to the newest year with
    any cash — understating is better than reporting nothing.
    """
    declarations = list(declarations)
    closed = {
        d["year"] for d in declarations
        if d.get("dividend_type") in YEAR_CLOSING_DECLARATIONS
        and d.get("cash_dividend_pct")
    }
    if closed:
        return max(closed)

    any_cash = {d["year"] for d in declarations if d.get("cash_dividend_pct")}
    return max(any_cash) if any_cash else None


def annual_cash_dividend(declarations: Iterable[dict], year: int) -> float | None:
    """Total cash dividend % for one year. None when the year paid no cash.

    **An ANNUAL row is the year's total, not another payment.** The archive
    lists both the total and the instalments that make it up, so summing every
    row double-counts:

        GP 2025:     Interim 110 + Final 105          — and ANNUAL says 215
        MARICO 2026: 500 + 600 + 500 + 475 = 2075     — and ANNUAL says 2075

    So the ANNUAL row wins where it exists. Components are summed only when the
    year has no total of its own — a year still mid-cycle, which is what
    latest_complete_dividend_year is for.
    """
    for_year = [d for d in declarations if d.get("year") == year and d.get("cash_dividend_pct")]

    totals = [d["cash_dividend_pct"] for d in for_year if d.get("dividend_type") == "ANNUAL"]
    if totals:
        return max(totals)

    return sum(d["cash_dividend_pct"] for d in for_year) or None
