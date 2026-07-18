"""What the fundamentals ingests actually landed (#57, #58).

The rest of the fundamentals tests use synthetic fixtures, so they prove the
parsers and prove nothing about the data. These query the real tables, so the
coverage claims are reproducible instead of living in a commit message.

They are the ones that would notice lankabd changing its markup, a scrape
silently emptying a table, or a schema drifting — which is the only class of
defect this codebase has actually suffered.
"""
import pytest

from backend import db

pytestmark = pytest.mark.integration

# Metrics spec §5 asks for, and the name each arrives under. `code` cannot be
# used: it is sector-scoped (ROA has 17 codes) — see scrapers/company_api.py.
SPEC_5_METRICS = [
    "Return on Equity (ROE)",
    "Return on Assets (ROA)",
    "Net Profit Margin",
    "Current Ratio",
    "Debt to Equity",
    "EBITDA Margin",
]


def _one(sql, params=None):
    return db.query_rows(sql, params)[0]


def test_every_fundamentals_table_has_a_current_view():
    for table in ("fundamentals_earnings", "fundamentals_dividends",
                  "fundamentals_ratios", "fundamentals_statements"):
        rows = db.query_rows(f"SELECT id FROM {db.current_view(table)} LIMIT 1")
        assert rows, f"{table}_current is empty — has the ingest run?"


@pytest.mark.parametrize("metric", SPEC_5_METRICS)
def test_spec_section_5_metric_is_present(metric):
    from google.cloud import bigquery

    r = _one(
        f"""SELECT COUNT(DISTINCT symbol) AS symbols
            FROM {db.current_view('fundamentals_ratios')}
            WHERE name = @name AND year = 2025""",
        [bigquery.ScalarQueryParameter("name", "STRING", metric)],
    )
    assert r["symbols"] > 50, f"{metric}: only {r['symbols']} symbols in 2025"


def test_the_statements_carry_all_three_types():
    rows = db.query_rows(f"""
        SELECT fs_type, COUNT(*) AS n
        FROM {db.current_view('fundamentals_statements')}
        GROUP BY fs_type
    """)
    types = {r["fs_type"] for r in rows}
    assert {"Balance Sheet", "Income Statement", "Cash Flow Statement"} <= types
    assert all(r["n"] > 1000 for r in rows)


def test_the_earnings_history_is_deep_enough_for_growth():
    # #59 computes EPS growth and PEG from this. The ratios API only goes back
    # three years; the dividend archive is why the history reaches 2014.
    r = _one(f"""
        SELECT MIN(year) AS lo, MAX(year) AS hi, COUNT(*) AS n
        FROM {db.current_view('fundamentals_earnings')}
        WHERE period = 'ANNUAL'
    """)
    assert r["lo"] <= 2015, f"annual history starts at {r['lo']} — too shallow for growth"
    assert r["hi"] >= 2025
    assert r["n"] > 3000


def test_a_symbol_year_never_holds_two_rows_for_one_ratio_code():
    # The row key is symbol|year|code. A duplicate would mean the append-only
    # view is silently dropping a fact (#52).
    r = _one(f"""
        SELECT COUNT(*) AS collisions FROM (
          SELECT symbol, year, code, COUNT(*) AS n
          FROM {db.current_view('fundamentals_ratios')}
          GROUP BY symbol, year, code HAVING n > 1
        )
    """)
    assert r["collisions"] == 0


def test_several_dividend_declarations_in_one_year_survive():
    # MARICO 2026 has five. symbol|year would have kept one.
    r = _one(f"""
        SELECT COUNT(*) AS n FROM {db.current_view('fundamentals_dividends')}
        WHERE symbol = 'MARICO' AND year = 2026
    """)
    assert r["n"] >= 4, f"only {r['n']} MARICO 2026 declarations survived"


def test_ratio_names_carry_no_stray_whitespace():
    # The source emits "Return on Assets (ROA) "; unstripped, it fragments the
    # metric across two names and #59 cannot join it.
    r = _one(f"""
        SELECT COUNT(*) AS untrimmed FROM {db.current_view('fundamentals_ratios')}
        WHERE name != TRIM(name)
    """)
    assert r["untrimmed"] == 0


# ── the #59 endpoint, against live data (the claims were prose before) ────────

def test_fundamentals_endpoint_returns_the_spec_5_metrics_for_gp():
    from backend import fundamentals_service as fs
    d = fs.get_fundamentals("GP")
    assert d["symbol"] == "GP" and d["price"]
    # All of spec §5, keyed by stable name (code is sector-scoped, #58).
    assert {"ROE", "ROA", "NET_MARGIN", "CURRENT_RATIO"} <= set(d["reported"])
    # GP pays cash; the yield is off the last complete year, not a mid-cycle one.
    assert d["derived"]["dividend_yield_pct"] > 0
    assert d["derived"]["dividend_year"] < 2026


def test_ab_bank_negative_equity_is_flagged_not_ranked_as_healthy():
    # The live trap #58 found: ROE 1.1986 is a loss over negative equity.
    from backend import fundamentals_service as fs
    d = fs.get_fundamentals("ABBANK")
    roe = d["reported"]["ROE"]
    assert roe["value"] > 1, "the raw ratio really does read as a healthy 120%"
    assert roe["sign_inverted"] is True, "but its sign is flagged inverted"
    assert d["derived"]["price_to_book"] is None, "negative equity is not 'cheap'"
