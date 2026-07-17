"""Tests for the company-API ingest (#58).

The fixtures mirror payloads observed live: GP's ratios (69 across 5 categories),
AB Bank's (33 across 3 — the sector variation that makes a wide table
untenable), and the empty ratioLists an unknown cid or a mutual fund returns.
"""
import pytest

from backend.scrapers import company_api as c


def _ratio(code, name="Total Asset Turnover", category="Asset Management & Asset Quality",
           result=0.826129, equation="158057490000.0000 / 191322941000.0000",
           base='"ISTEX90000" / "BS96033"'):
    return {"BaseEquation": base, "id": 20062, "Equation": equation, "CategoryOrder": 0,
            "Result": result, "Code": code, "Name": name, "Category": category,
            "SL": 1, "DisplayOrder": 210}


def _fs(code="BS96002", year=2021, fs_type="Balance Sheet",
        key="Property Plant & Equipment ", value=60387950000.0, order=15):
    return {"FSType": fs_type, "Year": year, "FSKey": key, "FSOrder": order,
            "FSValue": value, "IsVisible": True, "FSIsHighlighted": False,
            "FSIsInSummary": False, "FSCode": code}


# ── ratios ───────────────────────────────────────────────────────────────────

def test_parse_ratios_maps_a_year_block():
    payload = [{"year": 2025, "ratioList": [_ratio("RTAMAQ0210")]}]
    rows = c.parse_ratios("GP", payload)
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == "GP|2025|RTAMAQ0210"
    assert r["symbol"] == "GP" and r["year"] == 2025
    assert r["code"] == "RTAMAQ0210"
    assert r["name"] == "Total Asset Turnover"
    assert r["category"] == "Asset Management & Asset Quality"
    assert r["result"] == 0.826129
    # The audit trail: the figures and the formula behind the number.
    assert r["equation"] == "158057490000.0000 / 191322941000.0000"
    assert r["base_equation"] == '"ISTEX90000" / "BS96033"'


def test_the_same_code_in_different_years_is_a_different_row():
    # The year has to be in the key, or the append-only view (#52) would keep
    # only the most recently appended year and silently drop the history.
    payload = [
        {"year": 2025, "ratioList": [_ratio("A", result=1.0)]},
        {"year": 2024, "ratioList": [_ratio("A", result=2.0)]},
    ]
    rows = c.parse_ratios("GP", payload)
    assert [r["id"] for r in rows] == ["GP|2025|A", "GP|2024|A"]
    assert sorted(r["result"] for r in rows) == [1.0, 2.0]


def test_a_ratio_that_divides_two_negatives_is_reported_as_it_stands():
    """AB Bank's 2025 ROE really is 1.1986 — a loss over negative equity.

    -38.9bn / -32.4bn reads as a healthy 120%. The API reports what the
    statements say, and so do we: the equation is stored so a consumer can see
    the sign of the inputs rather than trusting the result. #59 has to check.
    """
    payload = [{"year": 2025, "ratioList": [_ratio(
        "RBPIR0010", name="Return on Equity (ROE)", result=1.198591,
        equation="-38891722887.0000 / -32447856712.0000")]}]
    r = c.parse_ratios("ABBANK", payload)[0]
    assert r["result"] == 1.198591, "not smoothed, not flagged, not dropped"
    assert r["equation"] == "-38891722887.0000 / -32447856712.0000"


def test_gross_profit_margin_of_one_is_reported_as_it_stands():
    # GP reads 1.0 because a telco reports no COGS line. #58 said: surface it,
    # do not smooth it.
    payload = [{"year": 2025, "ratioList": [_ratio(
        "RTPIR0100", name="Gross Profit Margin", result=1.0,
        equation="158057490000.0000 / 158057490000.0000")]}]
    r = c.parse_ratios("GP", payload)[0]
    assert r["result"] == 1.0
    assert r["equation"] == "158057490000.0000 / 158057490000.0000", \
        "the equation is what shows a reader why it is 1.0"


def test_empty_ratio_lists_are_not_an_error():
    # An unknown cid and a mutual fund both return 200 with empty lists.
    payload = [{"year": 2026, "ratioList": []}, {"year": 2025, "ratioList": []}]
    assert c.parse_ratios("SOMEFUND", payload) == []


def test_ratios_tolerate_a_missing_payload():
    assert c.parse_ratios("GP", None) == []
    assert c.parse_ratios("GP", []) == []


def test_a_ratio_without_a_code_is_skipped():
    # The code is the key; a row without one cannot be identified.
    payload = [{"year": 2025, "ratioList": [{"Name": "Mystery", "Result": 1.0}]}]
    assert c.parse_ratios("GP", payload) == []


def test_a_year_block_without_a_year_is_skipped():
    assert c.parse_ratios("GP", [{"ratioList": [_ratio("A")]}]) == []


def test_ratio_names_are_stripped_but_not_rewritten():
    # The source emits both "Return on Assets (ROA) " and "Return on Assets
    # (ROA)" for the same metric. Whitespace is lossless to remove.
    payload = [{"year": 2025, "ratioList": [
        _ratio("RTEXPIR0200", name="Return on Assets (ROA) ", category=" Profitability  "),
    ]}]
    r = c.parse_ratios("X", payload)[0]
    assert r["name"] == "Return on Assets (ROA)"
    assert r["category"] == "Profitability"


def test_the_same_metric_arrives_under_sector_specific_codes():
    """`code` is not a portable name for a metric — it is scoped to the sector.

    ROA lands under 17 codes live (RTEXPIR0200 textile, RENG0200 engineering,
    RBPIR0040 bank...). The row key symbol|year|code is still sound, but #59
    cannot ask for "ROA everywhere" by code.
    """
    textile = c.parse_ratios("TEXCO", [{"year": 2025, "ratioList": [
        _ratio("RTEXPIR0200", name="Return on Assets (ROA) ")]}])
    bank = c.parse_ratios("SOMEBANK", [{"year": 2025, "ratioList": [
        _ratio("RBPIR0040", name="Return on Assets (ROA)")]}])

    assert textile[0]["code"] != bank[0]["code"], "same metric, different codes"
    assert textile[0]["name"] == bank[0]["name"], "the trimmed name is what joins them"


def test_the_ratio_set_may_differ_by_sector():
    # GP reports 69 ratios across 5 categories, AB Bank 33 across 3. A column
    # per ratio would need a migration whenever that set changes.
    telco = c.parse_ratios("GP", [{"year": 2025, "ratioList": [
        _ratio("RTPIR0110", "Return on Equity (ROE)", "Profitability & Investment Return", 0.527954),
        _ratio("RTLL0310", "Current Ratio", "Liquidity & Leverage", 0.159223),
    ]}])
    bank = c.parse_ratios("ABBANK", [{"year": 2025, "ratioList": [
        _ratio("RTCFCA0410", "Capital Adequacy", "Cash Flow & Capital Adequacy", 0.11),
    ]}])
    assert {r["category"] for r in telco} != {r["category"] for r in bank}
    assert len(telco) == 2 and len(bank) == 1


# ── statements ───────────────────────────────────────────────────────────────

def test_parse_statements_maps_a_line_item():
    rows = c.parse_statements("GP", [_fs()])
    r = rows[0]
    assert r["id"] == "GP|2021|BS96002"
    assert r["fs_type"] == "Balance Sheet"
    assert r["fs_code"] == "BS96002"
    assert r["fs_key"] == "Property Plant & Equipment", "the source pads this with a space"
    assert r["fs_value"] == 60387950000.0
    assert r["fs_order"] == 15


def test_every_statement_line_gets_its_own_row():
    payload = [
        _fs("BS96002", 2021), _fs("BS96017", 2021),
        _fs("IS90000", 2021, "Income Statement"),
        _fs("BS96002", 2022),
    ]
    rows = c.parse_statements("GP", payload)
    assert len(rows) == 4
    assert len({r["id"] for r in rows}) == 4, "(year, fs_code) is the grain — verified unique live"


def test_all_three_statement_types_survive():
    payload = [_fs("A", 2021, "Balance Sheet"), _fs("B", 2021, "Income Statement"),
               _fs("C", 2021, "Cash Flow Statement")]
    rows = c.parse_statements("GP", payload)
    assert {r["fs_type"] for r in rows} == {"Balance Sheet", "Income Statement", "Cash Flow Statement"}


def test_statements_tolerate_a_missing_payload():
    assert c.parse_statements("GP", None) == []
    assert c.parse_statements("GP", []) == []


def test_a_line_without_a_code_or_year_is_skipped():
    assert c.parse_statements("GP", [{"FSType": "Balance Sheet", "FSValue": 1.0}]) == []
    assert c.parse_statements("GP", [{"Year": 2021, "FSValue": 1.0}]) == []


# ── ingest wiring ────────────────────────────────────────────────────────────

@pytest.fixture
def wired(monkeypatch):
    """Stub the network and the append; record what would be written."""
    appended = {}
    monkeypatch.setattr(c.db, "append_version", lambda t, rows: appended.setdefault(t, []).extend(rows))
    monkeypatch.setattr(c, "open_session", lambda: (object(), "tok"))
    monkeypatch.setattr(c, "symbol_by_cid", lambda s: {1: "ABBANK", 160: "GP"})
    monkeypatch.setattr(c.time, "sleep", lambda *_: None)
    return appended


def test_ingest_walks_every_company_and_appends_both_tables(wired, monkeypatch):
    def fake_api(session, token, path, cid, **params):
        if path == c.RATIOS:
            return [{"year": 2025, "ratioList": [_ratio("A")]}]
        return [_fs("BS96002", 2025)]

    monkeypatch.setattr(c, "_api", fake_api)
    counts = c.ingest()

    assert counts == {"companies": 2, "ratios": 2, "statements": 2, "failed": 0}
    assert {r["symbol"] for r in wired["fundamentals_ratios"]} == {"ABBANK", "GP"}
    assert set(wired) == {"fundamentals_ratios", "fundamentals_statements"}


def test_one_company_failing_does_not_abort_the_run(wired, monkeypatch):
    def flaky(session, token, path, cid, **params):
        if cid == 1:
            raise RuntimeError("500 from lankabd")
        return [{"year": 2025, "ratioList": [_ratio("A")]}] if path == c.RATIOS else [_fs()]

    monkeypatch.setattr(c, "_api", flaky)
    counts = c.ingest()

    # Append-only: a partial run adds facts and destroys none, unlike dataGrid
    # which replaces the universe and must refuse a partial scrape (#45).
    assert counts["failed"] == 1
    assert counts["companies"] == 2
    assert {r["symbol"] for r in wired["fundamentals_ratios"]} == {"GP"}


def test_a_company_with_no_financials_appends_nothing_and_is_not_a_failure(wired, monkeypatch):
    monkeypatch.setattr(c, "_api", lambda s, t, path, cid, **p:
                        [{"year": 2026, "ratioList": []}] if path == c.RATIOS else [])
    counts = c.ingest()
    assert counts["failed"] == 0, "an empty payload is normal for a mutual fund"
    assert counts["ratios"] == 0 and counts["statements"] == 0
    assert wired == {}, "nothing to append"


def test_no_companies_found_is_reported_not_crashed(monkeypatch):
    monkeypatch.setattr(c, "open_session", lambda: (object(), "tok"))
    monkeypatch.setattr(c, "symbol_by_cid", lambda s: {})
    counts = c.ingest()
    assert counts["companies"] == 0


def test_work_is_banked_in_batches_not_buffered_to_the_end(wired, monkeypatch):
    """Buffering all 414 companies means a crash at 400 throws away 828
    requests. Append-only is the reason a partial run is safe (#52) — so bank it.
    """
    appends = []
    monkeypatch.setattr(c.db, "append_version", lambda t, rows: appends.append((t, len(rows))))
    monkeypatch.setattr(c, "BATCH_SIZE", 2)
    monkeypatch.setattr(c, "symbol_by_cid", lambda s: {i: f"SYM{i}" for i in range(1, 6)})
    monkeypatch.setattr(c, "_api", lambda s, t, path, cid, **p:
                        [{"year": 2025, "ratioList": [_ratio("A")]}] if path == c.RATIOS else [_fs()])

    counts = c.ingest()

    assert counts["companies"] == 5 and counts["ratios"] == 5
    # 5 companies at BATCH_SIZE=2 -> flush at 2, at 4, and a final flush for the
    # 5th: three appends per table, not one at the end.
    ratio_appends = [n for t, n in appends if t == "fundamentals_ratios"]
    assert len(ratio_appends) == 3, f"expected batched appends, got {appends}"
    assert sum(ratio_appends) == 5, "every row still lands exactly once"


def test_a_company_failing_mid_way_does_not_half_ingest_it(wired, monkeypatch):
    # Ratios succeed, statements blow up. The company must not land with half
    # its data while also being counted as failed.
    def half_broken(session, token, path, cid, **params):
        if path == c.RATIOS:
            return [{"year": 2025, "ratioList": [_ratio("A")]}]
        raise RuntimeError("statements 500")

    monkeypatch.setattr(c, "_api", half_broken)
    counts = c.ingest()

    assert counts["failed"] == 2
    assert counts["ratios"] == 0, "no half-ingested company"
    assert counts["statements"] == 0


def test_ingest_respects_a_limit(wired, monkeypatch):
    monkeypatch.setattr(c, "_api", lambda s, t, path, cid, **p:
                        [{"year": 2025, "ratioList": [_ratio("A")]}] if path == c.RATIOS else [_fs()])
    assert c.ingest(limit=1)["companies"] == 1


def test_open_session_fails_loudly_without_a_token(monkeypatch):
    class _Resp:
        text = "<html><body>no token here</body></html>"

    class _Session:
        def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(c, "warm_session", lambda: _Session())
    # Without the token every call is a 400 with an empty body — a confusing
    # failure to debug 414 times over. announcement.py silently accepts a
    # missing token instead; see #61.
    with pytest.raises(RuntimeError, match="RequestVerificationToken"):
        c.open_session()
