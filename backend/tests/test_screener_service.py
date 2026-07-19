"""Offline tests for the screener (#71): whitelist rejects, preset resolution,
the bulk-read query shape, and derived filtering via valuation.py.
"""
import pytest
from google.cloud import bigquery

from backend import db, screener_service as ss
from backend.tests.fakes import FakeClient, rows as fake_rows


# ── whitelist / validation ──────────────────────────────────────────────────

def test_unknown_field_is_rejected():
    with pytest.raises(ss.InvalidFilter):
        ss._validate([{"field": "nonexistent", "op": "gt", "value": 1}])


def test_disallowed_operator_for_a_field_is_rejected():
    # sector only supports eq — gt is meaningless for a category.
    with pytest.raises(ss.InvalidFilter):
        ss._validate([{"field": "sector", "op": "gt", "value": "Banks"}])


def test_every_whitelisted_field_accepts_its_own_operators():
    for field, ops in ss.FILTER_WHITELIST.items():
        for op in ops:
            ss._validate([{"field": field, "op": op, "value": 1}])  # must not raise


def test_screen_raises_invalid_filter_for_bad_field(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient())
    with pytest.raises(ss.InvalidFilter):
        ss.screen(filters=[{"field": "rsi", "op": "gt", "value": 70}])


# ── preset resolution ────────────────────────────────────────────────────────

def test_resolve_filters_with_no_preset_or_filters_is_empty():
    assert ss.resolve_filters(None, None) == []


def test_each_preset_resolves_to_its_own_filters():
    for name, expected in ss.PRESETS.items():
        assert ss.resolve_filters(name, None) == expected


def test_unknown_preset_raises_invalid_filter():
    with pytest.raises(ss.InvalidFilter):
        ss.resolve_filters("momentum", None)  # a v2/technical preset, not shipped


def test_preset_filters_and_caller_filters_combine():
    combined = ss.resolve_filters("dividend_kings", [{"field": "sector", "op": "eq", "value": "Banks"}])
    assert combined == ss.PRESETS["dividend_kings"] + [{"field": "sector", "op": "eq", "value": "Banks"}]


# ── native WHERE: parameterized, not interpolated ───────────────────────────

def test_native_where_binds_values_as_parameters():
    where, params = ss._native_where([
        {"field": "pe", "op": "lte", "value": 15},
        {"field": "sector", "op": "eq", "value": "Banks"},
    ])
    assert "COALESCE(p.Forward_PE, p.Audited_PE) <= @nf0" in where
    assert "d.Sector = @nf1" in where
    assert "15" not in where and "Banks" not in where, "values must be bound, not interpolated"
    assert [p.value for p in params] == [15, "Banks"]
    assert params[1].type_ == "STRING"
    assert params[0].type_ == "FLOAT64"


def test_native_where_skips_derived_fields():
    where, params = ss._native_where([{"field": "pb", "op": "lte", "value": 1.5}])
    assert where == "TRUE"
    assert params == []


def test_native_where_with_no_filters_is_true():
    where, params = ss._native_where([])
    assert where == "TRUE"
    assert params == []


# ── bulk-read query shape ───────────────────────────────────────────────────

def test_bulk_rows_query_shape(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(db, "_client", client)
    ss._bulk_rows("TRUE", [])
    sql = client.calls[0]["sql"]
    assert "lankabd_datamatrix" in sql
    assert "lankabd_price_archive" in sql
    assert "fundamentals_earnings_current" in sql
    assert "ROW_NUMBER() OVER (PARTITION BY Symbol ORDER BY Date DESC)" in sql
    assert "LEFT JOIN" in sql, "a symbol missing a price/earnings row must still appear"


def test_cash_dividend_pcts_groups_by_symbol(monkeypatch):
    client = FakeClient(result_rows=fake_rows(
        {"symbol": "GP", "year": 2025, "dividend_type": "FINAL",
         "cash_dividend_pct": 105.0, "publish_date": "2026-01-01"},
        {"symbol": "GP", "year": 2025, "dividend_type": "INTERIM",
         "cash_dividend_pct": 110.0, "publish_date": "2025-08-01"},
    ))
    monkeypatch.setattr(db, "_client", client)
    pcts = ss._cash_dividend_pcts()
    # 2025 has no ANNUAL row, so both declarations sum (valuation.annual_cash_dividend).
    assert pcts["GP"] == pytest.approx(215.0)


# ── derived compute + filter (valuation.py reuse) ───────────────────────────

def test_with_derived_computes_pb_and_dividend_yield():
    rows = [{"symbol": "GP", "sector": "Telecom", "price": 200.0, "volume": 1000,
              "market_cap": 500.0, "pe": 12.0, "nav": 100.0}]
    out = ss._with_derived(rows, cash_pcts={"GP": 100.0})
    assert out[0]["pb"] == pytest.approx(2.0)                    # 200 / 100
    assert out[0]["dividend_yield"] == pytest.approx(5.0)          # (100% of 10 BDT face) / 200 * 100


def test_with_derived_pb_is_none_for_non_positive_nav():
    rows = [{"symbol": "X", "price": 50.0, "nav": -10.0}]
    out = ss._with_derived(rows, cash_pcts={})
    assert out[0]["pb"] is None


def test_apply_derived_filters_keeps_only_matching_rows():
    rows = [
        {"symbol": "A", "pb": 1.0, "dividend_yield": 2.0},
        {"symbol": "B", "pb": 3.0, "dividend_yield": 6.0},
    ]
    kept = ss._apply_derived_filters(rows, [{"field": "pb", "op": "lte", "value": 1.5}])
    assert [r["symbol"] for r in kept] == ["A"]


def test_apply_derived_filters_with_no_derived_filters_is_a_noop():
    rows = [{"symbol": "A", "pb": None}]
    assert ss._apply_derived_filters(rows, [{"field": "sector", "op": "eq", "value": "Banks"}]) is rows


def test_apply_derived_filters_none_never_satisfies_a_comparison():
    rows = [{"symbol": "A", "pb": None}]
    kept = ss._apply_derived_filters(rows, [{"field": "pb", "op": "lte", "value": 100}])
    assert kept == []


# ── screen() end to end ─────────────────────────────────────────────────────

class _TwoQueryClient:
    """Returns the bulk-join rows on the first query and dividend rows on the
    second — screen() always calls _bulk_rows then _cash_dividend_pcts, in
    that order.
    """
    def __init__(self, bulk_rows, dividend_rows):
        self._results = [fake_rows(*bulk_rows), fake_rows(*dividend_rows)]
        self.calls = []

    def query(self, sql, job_config=None):
        params = {}
        if job_config is not None:
            for p in job_config.query_parameters:
                params[p.name] = p.value
        self.calls.append({"sql": " ".join(sql.split()), "params": params})
        idx = len(self.calls) - 1
        rows = self._results[idx] if idx < len(self._results) else []
        return _Job(rows)


class _Job:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


def test_screen_end_to_end_applies_native_and_derived_filters(monkeypatch):
    client = _TwoQueryClient(
        bulk_rows=[
            {"symbol": "CHEAP", "sector": "Banks", "price": 100.0, "volume": 500,
             "pe": 10.0, "market_cap": 200.0, "nav": 100.0},
            {"symbol": "PRICEY", "sector": "Banks", "price": 500.0, "volume": 500,
             "pe": 10.0, "market_cap": 200.0, "nav": 50.0},
        ],
        dividend_rows=[],
    )
    monkeypatch.setattr(db, "_client", client)

    results = ss.screen(filters=[
        {"field": "pe", "op": "lte", "value": 20},   # native — pushed into SQL
        {"field": "pb", "op": "lte", "value": 1.5},   # derived — Python only
    ])

    assert [r["symbol"] for r in results] == ["CHEAP"]
    # The native filter must have been bound as a parameter on the bulk query.
    assert client.calls[0]["params"]["nf0"] == 20


def test_screen_respects_limit(monkeypatch):
    client = _TwoQueryClient(
        bulk_rows=[{"symbol": f"S{i}", "sector": "X", "price": 1.0, "volume": 1,
                    "pe": 1.0, "market_cap": 1.0, "nav": 1.0} for i in range(5)],
        dividend_rows=[],
    )
    monkeypatch.setattr(db, "_client", client)
    assert len(ss.screen(limit=2)) == 2


def test_screen_with_a_preset_applies_its_filters(monkeypatch):
    client = _TwoQueryClient(
        bulk_rows=[
            {"symbol": "VAL", "sector": "Banks", "price": 100.0, "volume": 500,
             "pe": 10.0, "market_cap": 200.0, "nav": 100.0},   # pe<=15, pb<=1.5: passes
            {"symbol": "EXP", "sector": "Banks", "price": 500.0, "volume": 500,
             "pe": 30.0, "market_cap": 200.0, "nav": 100.0},   # pe too high: fails native filter
        ],
        dividend_rows=[],
    )
    monkeypatch.setattr(db, "_client", client)
    results = ss.screen(preset="value")
    assert [r["symbol"] for r in results] == ["VAL"]
