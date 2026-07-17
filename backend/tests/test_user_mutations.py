"""Regression tests for the users-table mutation layer (#50, #52).

#40 replaced read-all + WRITE_TRUNCATE with scoped mutations for
watchlists/portfolios/alerts. user_service was missed and kept the old pattern
on the `users` table itself, where it was worse: the update applied its edit to
a discarded copy (a silent no-op — admin edits never worked), and deleting the
last user truncated the table with an empty DataFrame.

Writes now append a version and reads resolve `users_current` (#52), because
BigQuery's free tier forbids DML.
"""
import pytest

from backend import db, user_service
from backend.tests.fakes import FakeClient, rows as fake_rows

_ROW = {
    "id": "u1", "email": "alice@example.com", "phone": "0170",
    "full_name": "Alice", "role": "user", "password_hash": "hash",
    "created_at": "2026-07-01", "is_deleted": False,
}


class _AppendLog:
    def __init__(self):
        self.appends = []

    def __call__(self, table, rows):
        self.appends.append({"table": table, "rows": [dict(r) for r in rows]})


@pytest.fixture
def appended(monkeypatch):
    log = _AppendLog()
    monkeypatch.setattr(db, "append_version", log)
    return log


@pytest.fixture
def serving_alice(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(_ROW)))


@pytest.fixture
def serving_nobody(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClient())


def test_user_writes_never_truncate_and_never_use_dml(monkeypatch, appended):
    client = FakeClient(result_rows=fake_rows(_ROW))
    monkeypatch.setattr(db, "_client", client)
    user_service.update_user("u1", {"full_name": "New Name"})
    user_service.delete_user("u1")
    for call in client.calls:
        head = call["sql"].strip().upper()
        assert not head.startswith(("UPDATE", "DELETE", "INSERT")), call["sql"]
        assert "SELECT *" not in call["sql"] or "_current" in call["sql"]
    assert not hasattr(user_service, "pd"), "pandas was only needed for the truncate reload"


def test_update_user_appends_the_whole_merged_row(serving_alice, appended):
    assert user_service.update_user("u1", {"full_name": "Alice Smith"}) is True

    append = appended.appends[0]
    assert append["table"] == "users"
    row = append["rows"][0]
    assert row["full_name"] == "Alice Smith"
    # Untouched columns must survive, or the next version the view resolves
    # would null them out — including the password hash.
    assert row["password_hash"] == "hash"
    assert row["email"] == "alice@example.com"
    assert row["id"] == "u1"


def test_update_user_only_whitelisted_columns(serving_alice, appended):
    user_service.update_user("u1", {
        "full_name": "Ok", "role": "admin",
        "email": "hacker@example.com",   # not editable
        "password_hash": "pwned",        # not editable
        "id": "someone-else",            # not editable
        "is_deleted": True,              # not deletable via update
    })
    row = appended.appends[0]["rows"][0]
    assert row["full_name"] == "Ok" and row["role"] == "admin"
    assert row["email"] == "alice@example.com"
    assert row["password_hash"] == "hash"
    assert row["id"] == "u1"
    assert row["is_deleted"] is False


def test_update_user_with_no_editable_fields_is_a_noop(serving_alice, appended):
    assert user_service.update_user("u1", {"email": "x@y.com"}) is False
    assert appended.appends == []


def test_update_user_on_a_missing_user_is_false(serving_nobody, appended):
    assert user_service.update_user("ghost", {"full_name": "X"}) is False
    assert appended.appends == []


def test_delete_user_appends_a_tombstone(serving_alice, appended):
    assert user_service.delete_user("u1") is True
    row = appended.appends[0]["rows"][0]
    assert row["is_deleted"] is True
    assert row["id"] == "u1"


def test_delete_user_on_a_missing_user_is_false(serving_nobody, appended):
    assert user_service.delete_user("ghost") is False
    assert appended.appends == []


def test_reads_resolve_the_current_view_not_the_raw_table(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(db, "_client", client)
    user_service.list_users()
    user_service.get_user_by_id("u1")
    for call in client.calls:
        assert "users_current" in call["sql"], "a tombstoned user would still be visible"


# ── Multi-user survival (the regression #40 got, on the users table) ──────────

class _VersionStore:
    """Append-only rows plus `_current` semantics, in memory."""

    def __init__(self, initial=()):
        self.versions = [dict(r) for r in initial]

    def append(self, table, rows):
        self.versions.extend(dict(r) for r in rows)

    def current(self):
        latest = {}
        for row in self.versions:
            latest[row["id"]] = row
        return [r for r in latest.values() if not r.get("is_deleted")]


def test_updating_one_user_changes_only_that_user(monkeypatch):
    store = _VersionStore([
        dict(_ROW, id="u1", full_name="Alice"),
        dict(_ROW, id="u2", full_name="Bob", role="admin"),
    ])
    monkeypatch.setattr(db, "append_version", store.append)
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(dict(_ROW, id="u1"))))

    assert user_service.update_user("u1", {"full_name": "Alice Smith"}) is True

    by_id = {u["id"]: u for u in store.current()}
    # The old code applied the edit to a throwaway copy — this is the bug.
    assert by_id["u1"]["full_name"] == "Alice Smith"
    assert by_id["u2"]["full_name"] == "Bob"      # untouched
    assert by_id["u2"]["role"] == "admin"
    assert len(by_id) == 2                         # nobody vanished


def test_deleting_one_user_leaves_the_others(monkeypatch):
    store = _VersionStore([dict(_ROW, id=i) for i in ("u1", "u2", "u3")])
    monkeypatch.setattr(db, "append_version", store.append)
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(dict(_ROW, id="u2"))))

    assert user_service.delete_user("u2") is True
    assert {u["id"] for u in store.current()} == {"u1", "u3"}


def test_deleting_the_last_user_does_not_wipe_the_table(monkeypatch):
    # The old code loaded an EMPTY DataFrame with WRITE_TRUNCATE here, taking
    # the schema with it. An append cannot: the version log is still there.
    store = _VersionStore([dict(_ROW, id="only")])
    monkeypatch.setattr(db, "append_version", store.append)
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(dict(_ROW, id="only"))))

    assert user_service.delete_user("only") is True
    assert store.current() == []
    assert len(store.versions) == 2, "the tombstone is appended, nothing is erased"


def test_a_concurrent_signup_survives_an_update(monkeypatch):
    # The old read-all + reload dropped any row inserted between the SELECT and
    # the load job. An append never rewrites the other rows at all.
    store = _VersionStore([dict(_ROW, id="u1", full_name="Alice")])
    monkeypatch.setattr(db, "append_version", store.append)
    monkeypatch.setattr(db, "_client", FakeClient(result_rows=fake_rows(dict(_ROW, id="u1"))))

    store.append("users", [dict(_ROW, id="u-new", full_name="Newcomer")])  # concurrent signup
    user_service.update_user("u1", {"full_name": "Alice Smith"})

    assert {u["id"] for u in store.current()} == {"u1", "u-new"}
