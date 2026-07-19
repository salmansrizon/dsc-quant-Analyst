"""Read-path tests, newly possible now that reads go through db.query_rows (#46).

Before this, every service module did `bq = db.client()` at import time, so a
read could only be exercised against real BigQuery. Mutations were already
stubbable via db._client (see test_bq_mutations.py); these extend the same
pattern to reads — the asymmetry #41/#43 left behind.
"""
import pytest
from google.cloud import bigquery

from backend import db, market_service, watchlist_service, portfolio_service, alerts_service, user_service
from backend.tests.fakes import FakeClient, rows as fake_rows


@pytest.fixture
def fake_bq(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(db, "_client", client)
    return client


def test_query_rows_converts_bigquery_rows_to_plain_dicts(monkeypatch):
    # The client library yields Row objects, not dicts — converting them is the
    # one transformation query_rows performs.
    client = FakeClient(result_rows=fake_rows({"Symbol": "GP"}, {"Symbol": "BEXIMCO"}))
    monkeypatch.setattr(db, "_client", client)

    result = db.query_rows(
        "SELECT Symbol FROM t WHERE Sector = @sector",
        [bigquery.ScalarQueryParameter("sector", "STRING", "Banks")],
    )

    assert result == [{"Symbol": "GP"}, {"Symbol": "BEXIMCO"}]
    assert all(type(r) is dict for r in result), "rows must be plain dicts, not Row"
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
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows({"Symbol": "GP", "LTP": 1.5})))
    stock = market_service.get_stock("GP")
    assert stock == {"Symbol": "GP", "LTP": 1.5}
    assert type(stock) is dict  # callers index it and FastAPI serializes it


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


def test_get_user_by_email_maps_a_real_row_onto_UserResponse(monkeypatch):
    # The getters call r.get(...) with defaults, which only works once the Row
    # has been converted to a dict.
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows({
        "id": "u1", "email": "a@b.com", "phone": "0170",
        "full_name": "Test User", "role": "admin", "created_at": "2026-07-17",
    })))
    user = user_service.get_user_by_email("a@b.com")
    assert (user.id, user.email, user.role) == ("u1", "a@b.com", "admin")


def test_get_user_by_email_tolerates_columns_the_row_omits(monkeypatch):
    # Defaults exist for a reason: legacy rows predate some columns.
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows({
        "id": "u1", "email": "a@b.com", "created_at": None,
    })))
    user = user_service.get_user_by_email("a@b.com")
    assert user.role == "user" and user.phone == "" and user.full_name == ""
