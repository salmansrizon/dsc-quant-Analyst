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

    def load_table_from_json(self, rows, table, job_config=None):
        self.loaded.append({
            "table": table,
            "rows": list(rows),
            "disposition": job_config.write_disposition if job_config else None,
        })
        return _Done()

    def query(self, sql, job_config=None):
        params = {}
        if job_config is not None and job_config.query_parameters:
            params = {p.name: p.value for p in job_config.query_parameters}
        self.queries.append({
            "sql": " ".join(sql.split()), "job_config": job_config, "params": params,
        })
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
    assert row["updated_at"] == stamp.isoformat(), "load_table_from_json needs isoformat, not a datetime object"


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
    assert "ROW_NUMBER() OVER ( PARTITION BY id" in sql
    assert "_rn = 1" in sql
    # COALESCE is load-bearing: users predates is_deleted, and NOT NULL is NULL,
    # so those rows would silently vanish from the view.
    assert "NOT COALESCE(is_deleted, FALSE)" in sql


def test_ensure_current_view_can_key_on_another_column(client):
    db.ensure_current_view("watchlists", key="user_id")
    assert "PARTITION BY user_id" in client.queries[0]["sql"]


def test_the_view_breaks_updated_at_ties_in_favour_of_the_tombstone(client):
    # updated_at comes from Python's clock, so two appends can tie. Without a
    # tiebreaker ROW_NUMBER picks arbitrarily and a tombstone can lose to the
    # row it deletes — resurrecting deleted data.
    db.ensure_current_view("watchlists")
    sql = client.queries[0]["sql"]
    assert "ORDER BY updated_at DESC, COALESCE(is_deleted, FALSE) DESC" in sql


def test_there_is_no_compact_helper():
    # A SELECT-then-WRITE_TRUNCATE compaction destroys any row appended while it
    # runs — exactly the bug #40 was filed for. It needs a quiesced-writes
    # design, not a convenience helper (#52).
    assert not hasattr(db, "compact")


def test_find_current_reads_the_view_and_binds_its_values(client):
    db.find_current("portfolios", id="p1", user_id="u1")
    q = client.queries[0]
    assert "portfolios_current" in q["sql"]
    assert "WHERE id = @id AND user_id = @user_id" in " ".join(q["sql"].split())


def test_find_current_requires_a_filter(client):
    # An unfiltered "find one" would hand back an arbitrary user's row.
    with pytest.raises(ValueError):
        db.find_current("portfolios")


def test_tombstone_carries_the_whole_row(client):
    db.tombstone("watchlists", {"id": "w1", "user_id": "u1", "symbol": "GP"})
    row = client.loaded[0]["rows"][0]
    assert row["is_deleted"] is True
    assert row["symbol"] == "GP" and row["user_id"] == "u1"


def test_find_current_binds_values_as_parameters(client):
    db.find_current("portfolios", id="p1", user_id="u1")
    assert client.queries[0]["params"] == {"id": "p1", "user_id": "u1"}


def test_versioned_tables_derive_from_the_one_registry():
    # #62: VERSIONED_TABLES is derived from schema.TABLES, so the two can no
    # longer drift (they used to be independent dicts that had to agree).
    from backend.schema import TABLES
    assert db.VERSIONED_TABLES == {name: spec.key for name, spec in TABLES.items()}


def test_every_registered_table_can_be_versioned():
    from backend.schema import TABLES
    for table, spec in TABLES.items():
        names = {c for c, _ in spec.columns}
        assert {"id", "updated_at", "is_deleted"} <= names, f"{table} cannot be versioned"


def test_append_version_rejects_an_unregistered_table(monkeypatch):
    # The deepening (#62): a typo used to append to an autodetect table with no
    # _current view, silently losing the rows. Now it fails loudly, before any write.
    from backend.tests.fakes import AppendLog
    log = AppendLog()
    monkeypatch.setattr(db, "insert_rows", log)
    with pytest.raises(ValueError, match="not a registered versioned table"):
        db.append_version("portfoliosss", [{"id": "x"}])
    assert log.appends == [], "nothing may be written for an unknown table"
