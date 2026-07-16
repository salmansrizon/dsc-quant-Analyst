"""The ETL BigQueryHelper must be a shim over db, not a second bootstrap (#44)."""
import pytest

from backend import db
from backend.utils import bigquery_helper


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


def test_helper_project_and_dataset_track_db():
    assert bigquery_helper.BIGQUERY_PROJECT_ID == db.PROJECT
    assert bigquery_helper.BIGQUERY_DATASET_ID == db.DATASET


def test_credential_resolution_is_not_duplicated():
    # #44: the GCP_SERVICE_ACCOUNT_JSON -> temp-file dance lives only in db.py now.
    source = open(bigquery_helper.__file__, encoding="utf-8").read()
    assert "GCP_SERVICE_ACCOUNT_JSON" not in source
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in source
