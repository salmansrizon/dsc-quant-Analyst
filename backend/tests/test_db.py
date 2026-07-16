"""Tests for the unified BigQuery access point (tickets #41, #44)."""
from backend import db


def test_table_id_is_backtick_qualified():
    tid = db.table_id("watchlists")
    assert tid == f"`{db.PROJECT}.{db.DATASET}.watchlists`"
    assert tid.startswith("`") and tid.endswith("`")


def test_qualified_name_has_no_backticks():
    assert db.qualified_name("watchlists") == f"{db.PROJECT}.{db.DATASET}.watchlists"


def test_client_is_a_singleton():
    assert db.client() is db.client()


def test_api_modules_share_the_single_client():
    from backend import (
        market_service, watchlist_service, portfolio_service, alerts_service,
        user_service, exports,
    )
    for mod in (market_service, watchlist_service, portfolio_service, alerts_service, user_service):
        assert mod.bq is db.client()
    assert exports._get_bigquery_client() is db.client()


def test_table_helpers_delegate_to_db():
    from backend import market_service, watchlist_service, portfolio_service, alerts_service, user_service
    for mod in (market_service, watchlist_service, portfolio_service, alerts_service):
        assert mod._full_id is db.table_id
    assert user_service._uid is db.table_id
