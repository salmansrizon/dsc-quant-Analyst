"""Tests for the fundamentals ingest (#57).

The HTML fixtures below reproduce dirt observed live on lankabd.com, not
invented edge cases: the "Annuall" typo, blank dividend types (754 of them),
'-' for missing numbers, two different date formats, and MARICO's five
declarations in one year.
"""
from datetime import date

import pytest

from backend.scrapers import fundamentals as f


def _table(headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<html><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></html>"


ARCHIVE_HEADERS = [
    "Symbol", "Sector", "Year", "Dividend Type", "Cash Dividend %",
    "RIU/Stock Dividend %", "EPS/EPU", "NAV", "Dividend PublishDate in DSE",
    "Record Date", "AGM Date", "Duration", "Year End Date", "Remarks",
]
EARNINGS_HEADERS = ["Publish Date", "Symbol", "Sector", "Year", "Annual/Quarter", "EPS/EPU", "NAV"]


# ── normalisers ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    ("Annuall", "ANNUAL"),                 # sic — observed live
    ("Semi- Annual", "SEMI_ANNUAL"),       # sic
    ("Interim (12 Months)", "INTERIM"),    # the word wins, not the months
    ("  Annual  ", "ANNUAL"),              # whitespace is collapsed
    ("", "UNKNOWN"),                       # 754 rows are blank
    ("   ", "UNKNOWN"),
    ("Something New", "UNKNOWN"),          # a new variant must not crash
])
def test_normalise_dividend_type(raw, expected):
    # Only the cases that exercise logic — enumerating the lookup table back at
    # itself would assert nothing.
    assert f.normalise_dividend_type(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Annual", "ANNUAL"),
    ("Half Yearly", "H1"),
    ("1st Quarter", "Q1"),
    ("Nine months", "9M"),
    ("nine  months", "9M"),
    ("", "UNKNOWN"),
])
def test_normalise_period(raw, expected):
    assert f.normalise_period(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("2.54", 2.54), ("-2.24", -2.24), ("1,234.5", 1234.5),
    ("-", None), ("", None), (None, None), ("N/A", None), ("junk", None),
])
def test_parse_number(raw, expected):
    assert f.parse_number(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("15-Sep-2024", date(2024, 9, 15)),   # DividendArchive format
    ("2026-07-16", date(2026, 7, 16)),    # GetLatestEarnings format
    ("-", None), ("", None), ("not a date", None),
])
def test_parse_date(raw, expected):
    # A date, not a string: these load into BigQuery DATE columns, and pyarrow
    # will not coerce str -> date (#51 was that same mismatch).
    assert f.parse_date(raw) == expected


# ── dividend archive ─────────────────────────────────────────────────────────

def test_multiple_declarations_in_one_year_get_distinct_ids():
    """MARICO 2026 really has five rows. symbol|year would collapse them to one,
    and the append-only _current view resolves last-write-wins — so four real
    declarations would silently vanish.
    """
    rows = [
        ["MARICO", "Food & Allied", "2026", "Annual", "2075", "-", "206.09", "92.02",
         "30-Apr-2026", "-", "-", "-", "31-Mar-2026", ""],
        ["MARICO", "Food & Allied", "2026", "Final", "500", "-", "-", "-",
         "30-Apr-2026", "-", "-", "-", "31-Mar-2026", ""],
        ["MARICO", "Food & Allied", "2026", "Interim", "475", "-", "-", "-",
         "25-Jan-2026", "-", "-", "-", "31-Mar-2026", ""],
        ["MARICO", "Food & Allied", "2026", "Interim", "500", "-", "-", "-",
         "28-Oct-2025", "-", "-", "-", "31-Mar-2026", ""],
        ["MARICO", "Food & Allied", "2026", "Interim", "600", "-", "-", "-",
         "30-Jul-2025", "-", "-", "-", "31-Mar-2026", ""],
    ]
    dividends, _ = f.parse_dividend_archive(_table(ARCHIVE_HEADERS, rows))

    assert len(dividends) == 5
    assert len({d["id"] for d in dividends}) == 5, "every declaration needs its own id"
    assert sorted(d["cash_dividend_pct"] for d in dividends) == [475.0, 500.0, 500.0, 600.0, 2075.0]


@pytest.mark.parametrize("raw, expected", [
    # A stated month count is reported verbatim and never aliased. In MJLBD's
    # 18-month fiscal year the 12-month figure is NOT the annual one, so
    # "12 Months" -> ANNUAL would hand #59 an interim EPS to compute PEG from.
    ("Annual (18 Months)", "18M"),
    ("Annual (11 Months)", "11M"),
    ("Interim (12 Months)", "12M"),
    ("Final (06 Months)", "6M"),
    ("12 Months", "12M"),
    ("06 Months", "6M"),
    # No month count: fall back to what the type word says.
    ("Annual", "ANNUAL"),
    ("Annuall", "ANNUAL"),
    ("Semi-Annual", "H1"),
    ("Half Yearly", "H1"),
    # A bare Interim/Final genuinely does not say what it covers.
    ("Interim", "UNKNOWN"),
    ("Final", "UNKNOWN"),
    # Blank: inferred ANNUAL. All 747 are 2014-16, each the only EPS record for
    # its symbol-year, none sharing a symbol-year with a typed row.
    ("", "ANNUAL"),
])
def test_archive_period_reports_the_span_the_row_states(raw, expected):
    assert f.archive_period(raw) == expected


def test_one_year_reporting_three_periods_keeps_all_three():
    """MJLBD 2016 really reports three different EPS figures over three lengths.
    Labelling them all ANNUAL collapsed them onto one id and lost two.
    """
    rows = [
        ["MJLBD", "Fuel & Power", "2016", "Annual (18 Months)", "60", "-", "7.72", "35.51",
         "13-Oct-2016", "-", "-", "-", "30-Jun-2016", ""],
        ["MJLBD", "Fuel & Power", "2016", "Final (06 Months)", "30", "-", "3.48", "35.51",
         "13-Oct-2016", "-", "-", "-", "-", ""],
        ["MJLBD", "Fuel & Power", "2016", "Interim (12 Months)", "30", "-", "4.18", "35.08",
         "02-May-2016", "-", "-", "-", "-", ""],
    ]
    _, earnings = f.parse_dividend_archive(_table(ARCHIVE_HEADERS, rows))

    assert len(earnings) == 3
    assert len({e["id"] for e in earnings}) == 3, "three periods, three ids"
    assert sorted(e["eps"] for e in earnings) == [3.48, 4.18, 7.72]
    # Reported verbatim: 4.18 + 3.48 = 7.66 ~= 7.72, so the parts sum to the
    # 18-month whole — and the 12-month figure is not the annual one.
    assert {e["period"] for e in earnings} == {"18M", "12M", "6M"}


def test_eps_on_a_bare_interim_row_is_not_labelled_annual():
    # GP 2026: the archive reports EPS 10.52 on an Interim declaration, and
    # GetLatestEarnings independently calls that figure Half Yearly. Calling it
    # ANNUAL would be a fabrication.
    rows = [["GP", "Telecom", "2026", "Interim", "105", "-", "10.52", "41.51",
             "15-Jul-2026", "-", "-", "-", "31-Dec-2026", ""]]
    _, earnings = f.parse_dividend_archive(_table(ARCHIVE_HEADERS, rows))
    assert earnings[0]["period"] == "UNKNOWN"
    assert earnings[0]["period_raw"] == "Interim"


def test_only_rows_with_eps_become_earnings():
    # Interim/Final declarations carry no EPS — they are not earnings rows.
    rows = [
        ["GP", "Telecom", "2026", "Annual", "105", "-", "10.52", "41.51",
         "15-Jul-2026", "12-Aug-2026", "-", "-", "31-Dec-2026", ""],
        ["GP", "Telecom", "2026", "Interim", "50", "-", "-", "-",
         "01-Feb-2026", "-", "-", "-", "31-Dec-2026", ""],
    ]
    dividends, earnings = f.parse_dividend_archive(_table(ARCHIVE_HEADERS, rows))

    assert len(dividends) == 2
    assert len(earnings) == 1
    assert earnings[0]["eps"] == 10.52 and earnings[0]["nav"] == 41.51
    assert earnings[0]["period"] == "ANNUAL"
    assert earnings[0]["id"] == "GP|2026|ANNUAL|2026-07-15"


def test_archive_row_is_fully_mapped():
    rows = [["GP", "Telecommunication", "2026", "Annual", "105", "10", "10.52", "41.51",
             "15-Jul-2026", "12-Aug-2026", "20-Sep-2026", "-", "31-Dec-2026", "note"]]
    dividends, _ = f.parse_dividend_archive(_table(ARCHIVE_HEADERS, rows))
    d = dividends[0]
    assert d["symbol"] == "GP"
    assert d["year"] == 2026
    assert d["dividend_type"] == "ANNUAL"
    assert d["dividend_type_raw"] == "Annual"
    assert d["cash_dividend_pct"] == 105.0
    assert d["stock_dividend_pct"] == 10.0
    assert d["publish_date"] == date(2026, 7, 15)
    assert d["record_date"] == date(2026, 8, 12)
    assert d["agm_date"] == date(2026, 9, 20)
    assert d["year_end_date"] == date(2026, 12, 31)
    assert d["source"] == "dividend_archive"


def test_blank_dividend_type_is_kept_not_dropped():
    # 754 archive rows have a blank type. They still carry EPS.
    rows = [["ABC", "Bank", "2020", "", "5", "-", "1.23", "20.5",
             "01-Jan-2020", "-", "-", "-", "31-Dec-2020", ""]]
    dividends, earnings = f.parse_dividend_archive(_table(ARCHIVE_HEADERS, rows))
    assert dividends[0]["dividend_type"] == "UNKNOWN"
    assert dividends[0]["dividend_type_raw"] == ""
    assert len(earnings) == 1 and earnings[0]["eps"] == 1.23
    # The blank -> ANNUAL inference must stay auditable from the row itself.
    assert earnings[0]["period"] == "ANNUAL"
    assert earnings[0]["period_raw"] == ""


def test_rows_without_a_symbol_or_year_are_skipped():
    rows = [
        ["", "Bank", "2020", "Annual", "5", "-", "1.0", "2.0", "-", "-", "-", "-", "-", ""],
        ["ABC", "Bank", "", "Annual", "5", "-", "1.0", "2.0", "-", "-", "-", "-", "-", ""],
    ]
    dividends, earnings = f.parse_dividend_archive(_table(ARCHIVE_HEADERS, rows))
    assert dividends == [] and earnings == []


def test_symbols_are_upper_cased():
    rows = [["gp", "Telecom", "2026", "Annual", "1", "-", "1.0", "2.0",
             "-", "-", "-", "-", "-", ""]]
    dividends, earnings = f.parse_dividend_archive(_table(ARCHIVE_HEADERS, rows))
    assert dividends[0]["symbol"] == "GP"
    assert earnings[0]["id"].startswith("GP|")


# ── latest earnings ──────────────────────────────────────────────────────────

def test_latest_earnings_is_mapped_with_its_period():
    rows = [["2026-07-16", "BIFC", "Financial Institutions", "2026", "Half Yearly", "-3.26", "-136.84"]]
    out = f.parse_latest_earnings(_table(EARNINGS_HEADERS, rows))
    e = out[0]
    assert e["id"] == "BIFC|2026|H1|2026-07-16"
    assert e["period"] == "H1" and e["period_raw"] == "Half Yearly"
    assert e["eps"] == -3.26 and e["nav"] == -136.84
    assert e["publish_date"] == date(2026, 7, 16)
    assert e["source"] == "latest_earnings"


def test_an_unknown_period_still_ingests():
    rows = [["2026-07-16", "X", "S", "2026", "Trimester", "1.0", "2.0"]]
    out = f.parse_latest_earnings(_table(EARNINGS_HEADERS, rows))
    assert out[0]["period"] == "UNKNOWN"
    assert out[0]["period_raw"] == "Trimester", "the raw value survives for auditing"


def test_empty_page_yields_nothing():
    assert f.parse_latest_earnings("<html><body>nope</body></html>") == []
    assert f.parse_dividend_archive("<html><body>nope</body></html>") == ([], [])


# ── ingest wiring ────────────────────────────────────────────────────────────

def test_ingest_appends_to_both_tables(monkeypatch):
    appended = []
    monkeypatch.setattr(f.db, "append_version", lambda t, rows: appended.append((t, rows)))
    monkeypatch.setattr(f, "_fetch", lambda path: _table(
        ARCHIVE_HEADERS,
        [["GP", "Telecom", "2026", "Annual", "105", "-", "10.52", "41.51",
          "15-Jul-2026", "-", "-", "-", "31-Dec-2026", ""]],
    ) if path == f.DIVIDEND_ARCHIVE else _table(
        EARNINGS_HEADERS, [["2026-07-16", "GP", "Telecom", "2026", "1st Quarter", "2.5", "42.0"]],
    ))

    counts = f.ingest()

    assert counts == {"dividends": 1, "earnings_archive": 1, "earnings_latest": 1}
    tables = {t for t, _ in appended}
    assert tables == {"fundamentals_dividends", "fundamentals_earnings"}


def test_latest_earnings_wins_when_both_sources_report_the_same_period(monkeypatch):
    """Both sources can describe the same reporting period on the same publish
    date. The append-only view takes the last write, so the fresher source must
    be appended second.
    """
    appended = {}
    monkeypatch.setattr(f.db, "append_version", lambda t, rows: appended.setdefault(t, rows))
    monkeypatch.setattr(f, "_fetch", lambda path: _table(
        ARCHIVE_HEADERS,
        [["GP", "Telecom", "2026", "Annual", "105", "-", "1.00", "41.51",
          "16-Jul-2026", "-", "-", "-", "31-Dec-2026", ""]],
    ) if path == f.DIVIDEND_ARCHIVE else _table(
        EARNINGS_HEADERS, [["2026-07-16", "GP", "Telecom", "2026", "Annual", "9.99", "42.0"]],
    ))

    f.ingest()

    earnings = appended["fundamentals_earnings"]
    same_id = [e for e in earnings if e["id"] == "GP|2026|ANNUAL|2026-07-16"]
    assert len(same_id) == 2, "both sources describe the same period on the same date"
    assert same_id[-1]["source"] == "latest_earnings", "the fresher figure must be appended last"
    assert same_id[-1]["eps"] == 9.99
