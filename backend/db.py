"""Single BigQuery access point (tickets #41, #44).

Consolidates what used to be four independent client bootstraps (bq_service,
user_service, exports, utils/bigquery_helper) into one credential-resolution +
client + table-name helper. Every caller imports from here so they all share one
auth path instead of depending on whichever module set ambient ADC first.

The ETL/scraper layer reaches this through `utils.bigquery_helper.BigQueryHelper`,
now a thin shim over `client()` (#44).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _absolutize_adc_path() -> bool:
    """Make a relative GOOGLE_APPLICATION_CREDENTIALS survive the working directory.

    `.env` carries a repo-root-relative path. The API is launched from the repo
    root so it resolves; the ETL scripts run with cwd=backend, where the same
    path does not exist and the client library raises DefaultCredentialsError.
    Rewrite it to an absolute path so both entry points agree.

    Returns whether usable credentials are now configured — a path that points
    at nothing is not "configured", so the caller falls through to the local key.
    """
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path:
        return False
    if os.path.isabs(path):
        return os.path.exists(path)
    for base in (os.getcwd(), _REPO_ROOT):
        candidate = os.path.join(base, path)
        if os.path.exists(candidate):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = candidate
            return True
    logger.warning(
        "GOOGLE_APPLICATION_CREDENTIALS=%s does not resolve from cwd or the repo "
        "root; ignoring it and looking for a local key.", path,
    )
    return False


def _resolve_credentials() -> str | None:
    """Best-effort credential setup. Returns the service-account project_id if
    one was found. Never raises — falls through to ambient ADC so callers can
    still start in an environment that provides credentials another way.

    An explicit service-account key names its own project, so it decides
    PROJECT even when GOOGLE_APPLICATION_CREDENTIALS is already exported; only
    the pointing-at-a-file step is skipped in that case.
    """
    already_configured = _absolutize_adc_path()

    raw = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if raw:
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("Invalid GCP_SERVICE_ACCOUNT_JSON, ignoring: %s", e)
            return None
        if not already_configured:
            # On serverless (Vercel/Actions) the key arrives as an env var; the
            # client library only reads it from a file.
            temp_key = os.path.join(tempfile.gettempdir(), "gcp-key.json")
            with open(temp_key, "w", encoding="utf-8") as f:
                f.write(raw)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_key
        return info.get("project_id")

    # Local fallback: a service-account key checked out under backend/utils/.
    local = os.path.join(os.path.dirname(__file__), "utils", "dbt-test-420614-6c3337b4e737.json")
    if not already_configured and os.path.exists(local):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = local
        try:
            with open(local, "r", encoding="utf-8") as f:
                return json.load(f).get("project_id")
        except Exception:
            return None
    return None


_sa_project = _resolve_credentials()

_env_project = os.environ.get("BIGQUERY_PROJECT_ID")
if _env_project and _sa_project and _env_project != _sa_project:
    logger.warning(
        "BIGQUERY_PROJECT_ID mismatch: env=%s service_account=%s. Using the "
        "service-account project.", _env_project, _sa_project,
    )
# Service-account project wins (matches the prior bigquery_helper behavior),
# then the env override, then the default.
PROJECT = _sa_project or _env_project or "dbt-test-420614"
DATASET = os.environ.get("BIGQUERY_DATASET_ID") or "lankabd_dataset"

# Suffix of the latest-version view over an append-only table (#52).
CURRENT_SUFFIX = "_current"

# The append-only tables: every mutation appends a version, and reads go through
# `<table>_current`. Keyed by the column the latest version is resolved per.
VERSIONED_TABLES = {
    "users": "id",
    "watchlists": "id",
    "portfolios": "id",
    "price_alerts": "id",
    "fundamentals_earnings": "id",
    "fundamentals_dividends": "id",
    "fundamentals_ratios": "id",
    "fundamentals_statements": "id",
}

_client: bigquery.Client | None = None


def client() -> bigquery.Client:
    """Lazily-constructed singleton BigQuery client for the API layer."""
    global _client
    if _client is None:
        logger.info("BigQuery client init: project=%s dataset=%s", PROJECT, DATASET)
        _client = bigquery.Client(project=PROJECT)
    return _client


def qualified_name(name: str) -> str:
    """Bare fully-qualified table name: project.dataset.name (no backticks).

    This is the form the client library's table-reference arguments want; SQL
    text wants `table_id` instead.
    """
    return f"{PROJECT}.{DATASET}.{name}"


def table_id(name: str) -> str:
    """Backtick-quoted fully-qualified table id: `project.dataset.name`."""
    return f"`{qualified_name(name)}`"


def current_view(table: str) -> str:
    """Backtick-quoted id of a table's latest-version view (see append_version)."""
    return table_id(f"{table}{CURRENT_SUFFIX}")


def query_rows(sql: str, params: list["bigquery.ScalarQueryParameter"] | None = None) -> list[dict]:
    """Run a parameterized SELECT and return the rows as dicts.

    The read counterpart to append_version. Callers go through this rather than
    binding a client at import time, so tests can stub db._client on the read
    path exactly as they already do for mutations (ticket #46).
    """
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    return [dict(r) for r in client().query(sql, job_config=job_config).result()]


def insert_rows(table: str, rows: list[dict]) -> None:
    """Append rows via a load job (WRITE_APPEND, free-tier eligible)."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    job = client().load_table_from_dataframe(
        df, qualified_name(table),
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
        ),
    )
    job.result()


def append_version(table: str, rows: list[dict]) -> None:
    """Record a new version of each row. The only way to mutate a table (#52).

    Mutable tables are append-only logs: an update appends the full merged row,
    a delete appends a tombstone (`is_deleted=True`), and `<table>_current`
    resolves the latest version per id. Nothing is ever overwritten.

    This exists because BigQuery's free tier forbids DML entirely — `UPDATE`
    and `DELETE` return 403 (see #52). Appends are load jobs, which are free.
    It is also safer than the DML it replaces: an append cannot clobber a
    concurrent writer's rows, which is the failure #40 was filed for.

    Every row must carry `id`, `updated_at`, and `is_deleted`.
    """
    stamped = []
    for row in rows:
        if "id" not in row:
            raise ValueError(f"append_version({table}): row has no id to version by")
        row = dict(row)
        row.setdefault("updated_at", datetime.now(timezone.utc))
        row.setdefault("is_deleted", False)
        stamped.append(row)
    insert_rows(table, stamped)


def find_current(table: str, **match) -> dict | None:
    """One current row matching every column=value, or None.

    Reads `<table>_current`, so superseded versions and tombstones are already
    resolved away. Values are always bound as parameters — callers pass user
    input here (`find_current("portfolios", id=pid, user_id=uid)`), and scoping
    a lookup by owner is what stops one user reaching another's row.
    """
    if not match:
        raise ValueError("find_current needs at least one column to match on")
    where = " AND ".join(f"{col} = @{col}" for col in match)
    params = [
        bigquery.ScalarQueryParameter(col, "STRING", val)
        for col, val in match.items()
    ]
    rows = query_rows(
        f"SELECT * FROM {current_view(table)} WHERE {where} LIMIT 1", params
    )
    return rows[0] if rows else None


def tombstone(table: str, row: dict) -> None:
    """Mark a row deleted by appending a tombstone version of it.

    The whole row is carried over, not just its id: the view resolves the
    latest version per id, so a partial tombstone would be the row's new
    current state if it were ever un-deleted, and columns added later would
    read NULL.
    """
    append_version(table, [{
        **row,
        "is_deleted": True,
        "updated_at": datetime.now(timezone.utc),
    }])


def ensure_current_view(table: str, key: str = "id") -> None:
    """Create/replace `<table>_current`: the latest version per key, no tombstones.

    DDL is permitted on the free tier; DML is not (#52).

    Two details are load-bearing:

    - COALESCE on is_deleted: `users` predates the column, so its existing rows
      read NULL, and `NOT NULL` is NULL — those rows would silently vanish.
    - The is_deleted tiebreaker: updated_at comes from Python's clock, so two
      appends can tie (same microsecond, or skew between processes). Without a
      tiebreaker ROW_NUMBER picks arbitrarily, and a tombstone losing to the
      row it deletes would resurrect deleted data. Ordering tombstones first
      makes a tie fail safe: a delete never loses.
    """
    sql = f"""
    CREATE OR REPLACE VIEW {current_view(table)} AS
    SELECT * EXCEPT(_rn) FROM (
      SELECT *, ROW_NUMBER() OVER (
        PARTITION BY {key}
        ORDER BY updated_at DESC, COALESCE(is_deleted, FALSE) DESC
      ) AS _rn
      FROM {table_id(table)}
    )
    WHERE _rn = 1 AND NOT COALESCE(is_deleted, FALSE)
    """
    client().query(sql).result()


# No compact() here on purpose. The obvious implementation — SELECT the latest
# versions into the same table with WRITE_TRUNCATE — is precisely the pattern
# #40 was filed to kill: any row appended between the SELECT and the load job is
# destroyed, silently. On the free tier there is no atomic swap to make that
# safe, so compaction needs a quiesced-writes window and its own design. See
# the follow-up ticket. Until then the version log simply grows, which is what
# an append-only log is supposed to do.
