"""Read-path tests, newly possible now that reads go through db.query_rows (#46).

Before this, every service module did `bq = db.client()` at import time, so a
read could only be exercised against real BigQuery. Mutations were already
stubbable via db._client (see test_bq_mutations.py); these extend the same
pattern to reads — the asymmetry #41/#43 left behind.
"""
import pytest

from backend import db, market_service, watchlist_service, portfolio_service, alerts_service, user_service


class _FakeJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class _FakeClient:
    """Records SQL + params and replays canned rows."""

    def __init__(self, rows=()):
        self.calls = []
        self.rows = list(rows)

    def query(self, sql, job_config=None):
        params = {}
        if job_config is not None:
            for p in job_config.query_parameters:
                params[p.name] = p.value
        self.calls.append({"sql": " ".join(sql.split()), "params": params})
        return _FakeJob(self.rows)


@pytest.fixture
def fake_bq(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(db, "_client", client)
    return client


def test_query_rows_passes_params_and_maps_to_dicts(monkeypatch):
    client = _FakeClient(rows=[{"Symbol": "GP"}, {"Symbol": "BEXIMCO"}])
    monkeypatch.setattr(db, "_client", client)

    from google.cloud import bigquery
    rows = db.query_rows(
        "SELECT Symbol FROM t WHERE Sector = @sector",
        [bigquery.ScalarQueryParameter("sector", "STRING", "Banks")],
    )

    assert rows == [{"Symbol": "GP"}, {"Symbol": "BEXIMCO"}]
    assert client.calls[0]["params"] == {"sector": "Banks"}


def test_query_rows_with_no_params_is_fine(fake_bq):
    assert db.query_rows("SELECT 1") == []
    assert fake_bq.calls[0]["params"] == {}


def test_get_stock_upper_cases_the_symbol_and_scopes_the_query(fake_bq):
    market_service.get_stock("gp")
    call = fake_bq.calls[0]
    assert "WHERE Symbol = @symbol" in call["sql"]
    assert call["params"]["symbol"] == "GP"


def test_get_stock_returns_none_when_absent(fake_bq):
    assert market_service.get_stock("NOPE") is None


def test_get_stock_returns_the_row_when_present(monkeypatch):
    monkeypatch.setattr(db, "_client", _FakeClient(rows=[{"Symbol": "GP", "LTP": 1.5}]))
    assert market_service.get_stock("GP") == {"Symbol": "GP", "LTP": 1.5}


def test_list_stocks_filters_are_parameterized_not_interpolated(fake_bq):
    market_service.list_stocks(sector="Banks", search="gp")
    call = fake_bq.calls[0]
    assert "Sector = @sector" in call["sql"]
    assert "LOWER(Symbol) LIKE @search" in call["sql"]
    assert call["params"] == {"sector": "Banks", "search": "%gp%"}


def test_list_stocks_without_filters_uses_no_params(fake_bq):
    market_service.list_stocks()
    assert fake_bq.calls[0]["params"] == {}
    assert "WHERE TRUE" in fake_bq.calls[0]["sql"]


def test_top_movers_issues_two_scoped_queries(fake_bq):
    result = market_service.top_movers(limit=5)
    assert set(result) == {"gainers", "losers"}
    assert len(fake_bq.calls) == 2
    assert "ORDER BY __Change DESC" in fake_bq.calls[0]["sql"]
    assert "ORDER BY __Change ASC" in fake_bq.calls[1]["sql"]


def test_market_summary_returns_empty_dict_when_no_rows(fake_bq):
    assert market_service.market_summary() == {}


@pytest.mark.parametrize("call, expected_param", [
    (lambda: watchlist_service.get_watchlist("user-1"), "user-1"),
    (lambda: portfolio_service.get_portfolio("user-1"), "user-1"),
    (lambda: alerts_service.get_alerts("user-1"), "user-1"),
    (lambda: portfolio_service.portfolio_summary("user-1"), "user-1"),
])
def test_user_scoped_reads_pass_the_uid_as_a_param(fake_bq, call, expected_param):
    call()
    c = fake_bq.calls[0]
    assert c["params"]["uid"] == expected_param
    assert "@uid" in c["sql"]
    # A user's rows must never be selected by string interpolation.
    assert expected_param not in c["sql"]


def test_get_user_by_email_lowercases_and_parameterizes(fake_bq):
    user_service.get_user_by_email("  MiXeD@Example.COM ")
    c = fake_bq.calls[0]
    assert c["params"]["email"] == "mixed@example.com"
    assert "LOWER(email) = @email" in c["sql"]


def test_get_user_credentials_returns_none_when_absent(fake_bq):
    assert user_service.get_user_credentials("nobody@example.com") is None
