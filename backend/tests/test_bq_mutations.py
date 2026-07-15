"""
Offline regression tests for the row-level DML mutation layer (ticket #40).

These do NOT hit BigQuery — they stub bq_service.bq with a fake client that
records the SQL + params each mutation issues, proving the old read-all +
WRITE_TRUNCATE pattern (which destroyed other users' rows) is gone.
"""
import pytest

from backend import bq_service


class _FakeJob:
    def __init__(self):
        self.num_dml_affected_rows = 1

    def result(self):
        return self


class _FakeClient:
    """Records every query() call so tests can assert on the emitted SQL."""

    def __init__(self):
        self.calls = []

    def query(self, sql, job_config=None):
        params = {}
        if job_config is not None:
            for p in job_config.query_parameters:
                params[p.name] = p.value
        self.calls.append({"sql": " ".join(sql.split()), "params": params})
        return _FakeJob()


@pytest.fixture
def fake_bq(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(bq_service, "bq", client)
    return client


def test_rewrite_table_helper_is_gone():
    # The whole-table truncate helper must not exist anymore.
    assert not hasattr(bq_service, "_rewrite_table")
    assert hasattr(bq_service, "_execute_dml")


def test_remove_from_watchlist_issues_scoped_update(fake_bq):
    bq_service.remove_from_watchlist("user-1", "gp")
    assert len(fake_bq.calls) == 1
    call = fake_bq.calls[0]
    assert call["sql"].startswith("UPDATE")
    assert "SET is_deleted = TRUE" in call["sql"]
    assert "WHERE user_id = @uid AND symbol = @symbol" in call["sql"]
    # Never reads the whole table, never truncates.
    assert "SELECT *" not in call["sql"]
    assert call["params"]["uid"] == "user-1"
    assert call["params"]["symbol"] == "GP"  # upper-cased


def test_delete_alert_scopes_by_id_and_user(fake_bq):
    bq_service.delete_alert("alert-9", "user-1")
    call = fake_bq.calls[0]
    assert call["sql"].startswith("DELETE FROM")
    assert "WHERE id = @id AND user_id = @uid" in call["sql"]
    assert call["params"] == {"id": "alert-9", "uid": "user-1"}


def test_delete_portfolio_soft_deletes_scoped(fake_bq):
    bq_service.delete_portfolio("pf-1", "user-1")
    call = fake_bq.calls[0]
    assert "UPDATE" in call["sql"] and "SET is_deleted = TRUE" in call["sql"]
    assert "WHERE id = @id AND user_id = @uid" in call["sql"]
    assert call["params"]["id"] == "pf-1"
    assert call["params"]["uid"] == "user-1"


def test_update_portfolio_only_whitelisted_fields(fake_bq):
    ok = bq_service.update_portfolio(
        "pf-1", "user-1",
        {"quantity": 20, "notes": "add", "hacker_col": "DROP", "is_deleted": True},
    )
    assert ok is True
    call = fake_bq.calls[0]
    assert "quantity = @quantity" in call["sql"]
    assert "notes = @notes" in call["sql"]
    # Non-whitelisted keys must never reach the SQL.
    assert "hacker_col" not in call["sql"]
    assert "is_deleted = @is_deleted" not in call["sql"]
    assert "WHERE id = @id AND user_id = @uid AND is_deleted = FALSE" in call["sql"]
    assert call["params"]["quantity"] == 20


def test_update_portfolio_no_valid_fields_is_noop(fake_bq):
    ok = bq_service.update_portfolio("pf-1", "user-1", {"bogus": 1, "buy_price": None})
    assert ok is False
    assert fake_bq.calls == []  # nothing issued


def test_update_portfolio_returns_false_when_no_row_affected(fake_bq, monkeypatch):
    # Simulate a mutation that matched no row (wrong owner / missing id).
    def zero_dml(sql, job_config=None):
        job = _FakeJob()
        job.num_dml_affected_rows = 0
        fake_bq.calls.append({"sql": sql, "params": {}})
        return job

    monkeypatch.setattr(fake_bq, "query", zero_dml)
    ok = bq_service.update_portfolio("pf-x", "user-1", {"quantity": 5})
    assert ok is False
