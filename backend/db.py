"""Single BigQuery access point for the API layer (ticket #41).

Consolidates what used to be four independent client bootstraps (bq_service,
user_service, exports, utils/bigquery_helper) into one credential-resolution +
client + table-name helper. The API modules import from here so they all share
one auth path instead of depending on whichever module set ambient ADC first.

Note: backend/utils/bigquery_helper.py (the ETL/scraper layer, run standalone
with a different import context) is intentionally NOT migrated here yet — see
the follow-up note on ticket #41.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile

from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _resolve_credentials() -> str | None:
    """Best-effort credential setup. Returns the service-account project_id if
    one was found. Never raises — falls through to ambient ADC so the API can
    still start in an environment that provides credentials another way.
    """
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return None  # already configured by the environment

    raw = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if raw:
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("Invalid GCP_SERVICE_ACCOUNT_JSON, ignoring: %s", e)
            return None
        temp_key = os.path.join(tempfile.gettempdir(), "gcp-key.json")
        with open(temp_key, "w", encoding="utf-8") as f:
            f.write(raw)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_key
        return info.get("project_id")

    # Local fallback: a service-account key checked out under backend/utils/.
    local = os.path.join(os.path.dirname(__file__), "utils", "dbt-test-420614-6c3337b4e737.json")
    if os.path.exists(local):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = local
        try:
            with open(local, "r", encoding="utf-8") as f:
                return json.load(f).get("project_id")
        except Exception:
            return None
    return None


_sa_project = _resolve_credentials()

PROJECT = os.environ.get("BIGQUERY_PROJECT_ID") or _sa_project or "dbt-test-420614"
DATASET = os.environ.get("BIGQUERY_DATASET_ID") or "lankabd_dataset"

_client: bigquery.Client | None = None


def client() -> bigquery.Client:
    """Lazily-constructed singleton BigQuery client for the API layer."""
    global _client
    if _client is None:
        logger.info("BigQuery client init: project=%s dataset=%s", PROJECT, DATASET)
        _client = bigquery.Client(project=PROJECT)
    return _client


def table_id(name: str) -> str:
    """Backtick-quoted fully-qualified table id: `project.dataset.name`."""
    return f"`{PROJECT}.{DATASET}.{name}`"
