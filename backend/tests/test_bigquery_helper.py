"""The ETL BigQueryHelper must be a shim over db, not a second bootstrap (#44)."""
import pathlib
import subprocess
import sys

import pytest

from backend import db
from backend.utils import bigquery_helper

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]


class _FakeClient:
    def __init__(self):
        self.datasets_fetched = []

    def get_dataset(self, ref):
        self.datasets_fetched.append(ref)
        return object()


@pytest.fixture
def helper(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(db, "_client", fake)
    return bigquery_helper.BigQueryHelper(), fake


def test_helper_reuses_the_single_db_client(helper):
    bq, fake = helper
    assert bq.client is fake
    assert bq.client is db.client()
    assert fake.datasets_fetched == [f"{db.PROJECT}.{db.DATASET}"]


def test_helper_table_ids_come_from_db(helper):
    bq, _ = helper
    # The ETL scripts wrap this in their own backticks, so it must stay bare.
    assert bq._get_full_table_id("lankabd_datamatrix") == db.qualified_name("lankabd_datamatrix")
    assert "`" not in bq._get_full_table_id("lankabd_datamatrix")


def test_scraper_import_context_reaches_the_same_db():
    """The scrapers run `python <script>.py` with cwd=backend, where `backend`
    is not importable as a package — the path the in-process tests can't take.
    No client is constructed here; db.client() is lazy.
    """
    script = (
        "import db\n"
        "from utils.bigquery_helper import BigQueryHelper\n"
        "from utils import bigquery_helper\n"
        "assert bigquery_helper.db is db, 'shim bound a second db module'\n"
        "print(db.PROJECT, db.DATASET)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=BACKEND_DIR,
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == [db.PROJECT, db.DATASET]
