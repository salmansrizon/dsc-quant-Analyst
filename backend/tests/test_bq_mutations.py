"""Offline regression tests for the append-only mutation layer (#40, #43, #52).

History matters here. #40 replaced a read-all + WRITE_TRUNCATE pattern that
destroyed other users' rows with scoped row-level DML. #52 found that DML is
forbidden on BigQuery's free tier — every mutation 403'd — so mutations now
append a new version and reads resolve `<table>_current`.

The property under test never changed: **one user's mutation must not touch
another user's rows.** The survival tests below assert it against a fake that
actually stores what was appended, not one that only records SQL text.
"""
import pytest

from backend import db, watchlist_service, portfolio_service, alerts_service
from backend.tests.fakes import AppendLog, FakeClient, VersionStore, rows as fake_rows


@pytest.fixture
def appended(monkeypatch):
    log = AppendLog()
    monkeypatch.setattr(db, "append_version", log)
    return log


@pytest.fixture
def no_rows(monkeypatch):
    """The current view returns nothing: the target does not exist."""
    monkeypatch.setattr(db, "_client", FakeClient())


def test_no_service_issues_dml(monkeypatch):
    # DML is a 403 on the free tier (#52). Nothing may emit UPDATE/DELETE/INSERT.
    client = FakeClient()
    monkeypatch.setattr(db, "_client", client)
    for fn in (
        lambda: watchlist_service.remove_from_watchlist("u1", "GP"),
        lambda: portfolio_service.delete_portfolio("p1", "u1"),
        lambda: alerts_service.delete_alert("a1", "u1"),
    ):
        fn()
    for call in client.calls:
        head = call["sql"].strip().upper()
        assert not head.startswith(("UPDATE", "DELETE", "INSERT", "MERGE")), call["sql"]


def test_execute_dml_is_gone():
    # Kept as a tripwire: reintroducing it would 403 in production.
    assert not hasattr(db, "execute_dml")


# ── Mutations append a version rather than editing in place ───────────────────

def test_remove_from_watchlist_appends_a_tombstone(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "w1", "user_id": "u1", "symbol": "GP", "added_at": "2026-07-01"},
    )))
    assert watchlist_service.remove_from_watchlist("u1", "gp") is True

    append = appended.appends[0]
    assert append["table"] == "watchlists"
    row = append["rows"][0]
    assert row["is_deleted"] is True
    assert row["id"] == "w1"           # tombstones the same row, not a new one
    assert row["user_id"] == "u1"


def test_remove_from_watchlist_on_a_missing_entry_appends_nothing(no_rows, appended):
    assert watchlist_service.remove_from_watchlist("u1", "GP") is False
    assert appended.appends == []


def test_delete_alert_appends_a_tombstone(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "a1", "user_id": "u1", "symbol": "GP", "is_triggered": False},
    )))
    assert alerts_service.delete_alert("a1", "u1") is True
    assert appended.appends[0]["rows"][0]["is_deleted"] is True


def test_delete_portfolio_appends_a_tombstone(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "p1", "user_id": "u1", "symbol": "GP", "quantity": 10},
    )))
    assert portfolio_service.delete_portfolio("p1", "u1") is True
    assert appended.appends[0]["rows"][0]["is_deleted"] is True


def test_lookups_are_scoped_to_the_owner(monkeypatch):
    # Guessing an id must not reach another user's row.
    client = FakeClient()
    monkeypatch.setattr(db, "_client", client)
    portfolio_service.delete_portfolio("p1", "u1")
    call = client.calls[0]
    assert "WHERE id = @id AND user_id = @user_id" in call["sql"]
    assert call["params"] == {"id": "p1", "user_id": "u1"}
    # Values are bound, never interpolated into the SQL.
    assert "p1" not in call["sql"] and "u1" not in call["sql"]


def test_update_portfolio_appends_the_whole_merged_row(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "p1", "user_id": "u1", "symbol": "GP", "quantity": 10,
         "buy_price": 100.0, "notes": "old", "is_deleted": False},
    )))
    assert portfolio_service.update_portfolio("p1", "u1", {"quantity": 25, "notes": "new"}) is True

    row = appended.appends[0]["rows"][0]
    assert row["quantity"] == 25 and row["notes"] == "new"
    # Untouched columns must survive: a partial append would null them out in
    # the next version the view resolves.
    assert row["symbol"] == "GP" and row["buy_price"] == 100.0
    assert row["id"] == "p1" and row["user_id"] == "u1"


def test_update_portfolio_only_whitelisted_fields(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "p1", "user_id": "u1", "symbol": "GP", "quantity": 10, "is_deleted": False},
    )))
    portfolio_service.update_portfolio("p1", "u1", {
        "quantity": 25, "user_id": "someone-else", "is_deleted": True, "hacker_col": "x",
    })
    row = appended.appends[0]["rows"][0]
    assert row["quantity"] == 25
    assert row["user_id"] == "u1"        # not reassignable
    assert row["is_deleted"] is False    # not deletable via update
    assert "hacker_col" not in row


def test_update_portfolio_no_valid_fields_is_a_noop(no_rows, appended):
    assert portfolio_service.update_portfolio("p1", "u1", {"bogus": 1, "buy_price": None}) is False
    assert appended.appends == []


def test_update_portfolio_on_a_missing_holding_is_false(no_rows, appended):
    assert portfolio_service.update_portfolio("p-x", "u1", {"quantity": 5}) is False
    assert appended.appends == []


def test_add_to_watchlist_is_idempotent(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "w1", "user_id": "u1", "symbol": "GP", "added_at": "2026-07-01"},
    )))
    result = watchlist_service.add_to_watchlist("u1", "GP")
    assert result["id"] == "w1"
    assert appended.appends == [], "re-adding must not append a second version"


def test_mark_triggered_skips_already_triggered(monkeypatch, appended):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(
        {"id": "a1", "user_id": "u1", "symbol": "GP", "is_triggered": False},
    )))
    assert alerts_service.mark_triggered(["a1", "a2"]) == 1
    row = appended.appends[0]["rows"][0]
    assert row["is_triggered"] is True and row["triggered_at"] is not None
    # The query itself filters out already-triggered alerts, so a re-run is safe.


def test_mark_triggered_with_no_ids_does_nothing(no_rows, appended):
    assert alerts_service.mark_triggered([]) == 0
    assert appended.appends == []


# ── Multi-user survival: the regression #40 was filed for ─────────────────────

@pytest.fixture
def store(monkeypatch):
    s = VersionStore()
    monkeypatch.setattr(db, "append_version", s.append)
    return s


def _serve(monkeypatch, rows_out):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(*rows_out)))


def test_removing_user1_watchlist_item_leaves_user2_untouched(monkeypatch, store):
    store.append("watchlists", [
        {"id": "w1", "user_id": "u1", "symbol": "GP", "is_deleted": False},
        {"id": "w2", "user_id": "u2", "symbol": "GP", "is_deleted": False},
        {"id": "w3", "user_id": "u2", "symbol": "BEXIMCO", "is_deleted": False},
    ])
    # The view hands back only u1's row for GP.
    _serve(monkeypatch, [{"id": "w1", "user_id": "u1", "symbol": "GP", "added_at": None}])
    watchlist_service.remove_from_watchlist("u1", "GP")

    assert store.current_for(user_id="u1") == []                       # u1's row gone
    assert sorted(r["symbol"] for r in store.current_for(user_id="u2")) == ["BEXIMCO", "GP"]


def test_deleting_user1_alert_leaves_user2_alerts(monkeypatch, store):
    store.append("price_alerts", [
        {"id": "a1", "user_id": "u1", "is_deleted": False},
        {"id": "a2", "user_id": "u2", "is_deleted": False},
        {"id": "a3", "user_id": "u2", "is_deleted": False},
    ])
    _serve(monkeypatch, [{"id": "a1", "user_id": "u1", "is_triggered": False}])
    alerts_service.delete_alert("a1", "u1")

    assert {r["id"] for r in store.current()} == {"a2", "a3"}


def test_updating_user1_holding_leaves_user2_holdings(monkeypatch, store):
    store.append("portfolios", [
        {"id": "p1", "user_id": "u1", "quantity": 10, "is_deleted": False},
        {"id": "p2", "user_id": "u2", "quantity": 99, "is_deleted": False},
    ])
    _serve(monkeypatch, [{"id": "p1", "user_id": "u1", "quantity": 10, "is_deleted": False}])
    portfolio_service.update_portfolio("p1", "u1", {"quantity": 25})

    by_id = {r["id"]: r for r in store.current()}
    assert by_id["p1"]["quantity"] == 25
    assert by_id["p2"]["quantity"] == 99   # untouched
    assert len(by_id) == 2                  # nobody vanished


def test_a_concurrent_append_survives_another_users_mutation(monkeypatch, store):
    """The old truncate dropped rows written during the mutation. An append
    physically cannot: it never rewrites anyone else's rows.
    """
    store.append("watchlists", [{"id": "w1", "user_id": "u1", "symbol": "GP", "is_deleted": False}])
    _serve(monkeypatch, [{"id": "w1", "user_id": "u1", "symbol": "GP", "added_at": None}])

    # u2 adds a row midway through u1's removal.
    store.append("watchlists", [{"id": "w9", "user_id": "u2", "symbol": "SQUARE", "is_deleted": False}])
    watchlist_service.remove_from_watchlist("u1", "GP")

    assert {r["id"] for r in store.current()} == {"w9"}
