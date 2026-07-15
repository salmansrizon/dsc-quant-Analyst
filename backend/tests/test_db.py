"""Tests for the unified BigQuery access point (ticket #41)."""
from backend import db


def test_table_id_is_backtick_qualified():
    tid = db.table_id("watchlists")
    assert tid == f"`{db.PROJECT}.{db.DATASET}.watchlists`"
    assert tid.startswith("`") and tid.endswith("`")


def test_client_is_a_singleton():
    assert db.client() is db.client()


def test_api_modules_share_the_single_client():
    from backend import bq_service, user_service, exports
    assert bq_service.bq is db.client()
    assert user_service.bq is db.client()
    assert exports._get_bigquery_client() is db.client()


def test_table_helpers_delegate_to_db():
    from backend import bq_service, user_service
    assert bq_service._full_id is db.table_id
    assert user_service._uid is db.table_id
