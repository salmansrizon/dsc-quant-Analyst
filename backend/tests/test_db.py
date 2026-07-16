"""Tests for the unified BigQuery access point (tickets #41, #44)."""
import json
import os

from backend import db

_KEY = json.dumps({"project_id": "sa-project", "type": "service_account"})


def test_service_account_json_names_the_project_even_when_adc_is_exported(monkeypatch, tmp_path):
    # #44: the ETL used to take its project from GCP_SERVICE_ACCOUNT_JSON
    # unconditionally. If an exported GOOGLE_APPLICATION_CREDENTIALS suppressed
    # that, the scrapers would silently write to the default project instead.
    other = tmp_path / "other.json"
    other.write_text(_KEY, encoding="utf-8")  # must exist, or it is not "configured"
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(other))
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", _KEY)
    assert db._resolve_credentials() == "sa-project"
    # ...but it must not repoint an already-configured environment at a temp file.
    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(other)


def test_service_account_json_is_written_to_a_file_when_adc_is_absent(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", _KEY)
    assert db._resolve_credentials() == "sa-project"
    written = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    assert json.loads(open(written, encoding="utf-8").read())["project_id"] == "sa-project"


def test_relative_adc_path_is_absolutized_so_cwd_cannot_break_it(monkeypatch, tmp_path):
    # #44 regression: .env carries a repo-root-relative GOOGLE_APPLICATION_CREDENTIALS.
    # The API runs from the repo root so it resolved; the ETL scripts run with
    # cwd=backend, where the same path does not exist -> DefaultCredentialsError.
    key = tmp_path / "key.json"
    key.write_text(_KEY, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "key.json")  # relative

    db._resolve_credentials()
    resolved = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    assert os.path.isabs(resolved)
    assert os.path.exists(resolved)


def test_adc_path_pointing_at_nothing_falls_through_to_the_local_key(monkeypatch):
    # A path that resolves nowhere is not "configured" — it must not suppress
    # the local-key fallback, or the scrapers die on a stale .env entry.
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "no/such/file.json")
    assert db._absolutize_adc_path() is False


def test_invalid_service_account_json_does_not_raise(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", "{not json")
    assert db._resolve_credentials() is None


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
