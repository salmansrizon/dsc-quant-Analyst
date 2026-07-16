"""The admin exports must name tables that actually exist (#49).

test_admin_exports.py cannot catch this: its fixtures sign up a user against real
BigQuery and error at setup, so the export bodies never run. These tests stub the
client instead and assert on the SQL the exports emit, so a wrong table name fails
here regardless of whether BigQuery is reachable.
"""
import pytest

from backend import db, exports

# Tables the ETL actually writes. `announcements` and `price_archive` (unprefixed)
# have never existed in the dataset — pointing an export at them is the #49 bug.
ETL_TABLES = {"lankabd_announcements", "lankabd_price_archive", "lankabd_datamatrix"}


class _CapturingClient:
    def __init__(self):
        self.sql = []

    def query(self, sql, job_config=None):
        self.sql.append(sql)
        return _EmptyJob()


class _EmptyJob:
    def result(self):
        return [{"Symbol": "GP", "Date": "2026-07-16"}]


@pytest.fixture
def captured(monkeypatch):
    client = _CapturingClient()
    monkeypatch.setattr(db, "_client", client)
    return client


def test_export_announcements_reads_the_prefixed_table(captured):
    exports.export_announcements()
    sql = captured.sql[0]
    assert db.table_id("lankabd_announcements") in sql
    assert "`announcements`" not in sql
    # The table has no LTP column — selecting it fails even with the right name.
    assert "LTP" not in sql


def test_export_price_archive_reads_the_prefixed_table(captured):
    exports.export_price_archive()
    sql = captured.sql[0]
    assert db.table_id("lankabd_price_archive") in sql
    assert "`price_archive`" not in sql


def test_export_master_dataset_reads_the_prefixed_table(captured):
    exports.export_master_dataset()
    assert db.table_id("lankabd_datamatrix") in captured.sql[0]


def test_no_export_names_a_table_the_etl_never_writes(captured):
    exports.export_announcements()
    exports.export_price_archive()
    exports.export_master_dataset()
    for sql in captured.sql:
        table = sql.split("FROM ")[1].split()[0].strip("`").split(".")[-1]
        assert table in ETL_TABLES, f"export reads {table!r}, which no writer produces"
