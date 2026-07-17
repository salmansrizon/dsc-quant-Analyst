"""Tests for the append-only primitives in db.py (ticket #52).

BigQuery's free tier forbids DML — UPDATE/DELETE/INSERT return 403 — so
mutations append a version and `<table>_current` resolves the latest one.
"""
import datetime as dt

import pytest

from backend import db


class _RecordingClient:
    def __init__(self):
        self.loaded = []
        self.queries = []

    def load_table_from_dataframe(self, df, table, job_config=None):
        self.loaded.append({
            "table": table,
            "rows": df.to_dict("records"),
            "disposition": job_config.write_disposition if job_config else None,
        })
        return _Done()

    def query(self, sql, job_config=None):
        self.queries.append({"sql": " ".join(sql.split()), "job_config": job_config})
        return _Done()


class _Done:
    num_dml_affected_rows = 0

    def result(self):
        return []


@pytest.fixture
def client(monkeypatch):
    c = _RecordingClient()
    monkeypatch.setattr(db, "_client", c)
    return c


def test_current_view_names_the_view():
    assert db.current_view("watchlists") == db.table_id("watchlists_current")


def test_append_version_writes_via_a_free_load_job(client):
    db.append_version("watchlists", [{"id": "w1", "symbol": "GP"}])
    load = client.loaded[0]
    assert load["disposition"] == "WRITE_APPEND", "a truncate would destroy other rows"
    assert client.queries == [], "no DML — it is a 403 on the free tier"


def test_append_version_defaults_the_version_columns(client):
    db.append_version("watchlists", [{"id": "w1", "symbol": "GP"}])
    row = client.loaded[0]["rows"][0]
    assert row["is_deleted"] is False
    assert isinstance(row["updated_at"], (dt.datetime,)) or row["updated_at"] is not None


def test_append_version_keeps_explicit_version_columns(client):
    stamp = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    db.append_version("watchlists", [
        {"id": "w1", "symbol": "GP", "is_deleted": True, "updated_at": stamp},
    ])
    row = client.loaded[0]["rows"][0]
    assert row["is_deleted"] is True
    assert row["updated_at"] == stamp


def test_append_version_rejects_a_row_without_an_id(client):
    with pytest.raises(ValueError, match="id"):
        db.append_version("watchlists", [{"symbol": "GP"}])
    assert client.loaded == []


def test_append_version_does_not_mutate_the_caller_dict(client):
    row = {"id": "w1", "symbol": "GP"}
    db.append_version("watchlists", [row])
    assert row == {"id": "w1", "symbol": "GP"}


def test_ensure_current_view_resolves_latest_and_hides_tombstones(client):
    db.ensure_current_view("watchlists")
    sql = client.queries[0]["sql"]
    assert sql.startswith("CREATE OR REPLACE VIEW")
    assert "ROW_NUMBER() OVER ( PARTITION BY id ORDER BY updated_at DESC )" in sql
    assert "_rn = 1" in sql
    # COALESCE is load-bearing: users predates is_deleted, and NOT NULL is NULL,
    # so those rows would silently vanish from the view.
    assert "NOT COALESCE(is_deleted, FALSE)" in sql


def test_ensure_current_view_can_key_on_another_column(client):
    db.ensure_current_view("watchlists", key="user_id")
    assert "PARTITION BY user_id" in client.queries[0]["sql"]


def test_compact_writes_to_the_table_without_dml(client):
    db.compact("watchlists")
    q = client.queries[0]
    # A query job with a destination table is allowed on the free tier; DML is not.
    assert q["sql"].strip().upper().startswith("SELECT")
    # The library normalizes the destination into a TableReference.
    assert str(q["job_config"].destination) == db.qualified_name("watchlists")
    assert q["job_config"].write_disposition == "WRITE_TRUNCATE"


def test_versioned_tables_all_have_a_view_key():
    # bootstrap_tables iterates this; a table listed without a schema would fail there.
    from backend.bootstrap_tables import SCHEMAS
    assert set(db.VERSIONED_TABLES) == set(SCHEMAS)
    for table, columns in SCHEMAS.items():
        names = {c for c, _ in columns}
        assert {"id", "updated_at", "is_deleted"} <= names, f"{table} cannot be versioned"
