"""ETL/scraper BigQuery facade — a thin shim over backend/db.py (ticket #44).

This module used to carry its own copy of the credential resolution, project
selection and client construction that `db.py` now owns. It keeps the class
shape (`client`, `_get_full_table_id`, `get_last_date`, `upload_dataframe`) that
the standalone scripts already call, so nothing about how they're run changes.

Import note: the scrapers run with cwd=backend (`from utils.bigquery_helper
import ...`), while the API imports this package-qualified, so `db` has to be
reachable both ways.
"""
import logging
import re

import pandas as pd
from google.cloud import bigquery

try:
    from backend import db
except ImportError:  # standalone scripts: cwd=backend, so backend/ is sys.path[0]
    import db

logger = logging.getLogger(__name__)

# Kept as module-level names because the ETL scripts import them directly.
BIGQUERY_PROJECT_ID = db.PROJECT
BIGQUERY_DATASET_ID = db.DATASET


class BigQueryHelper:
    def __init__(self):
        self.client = db.client()
        self.dataset_id = db.DATASET
        self._ensure_dataset()

    def _ensure_dataset(self):
        dataset_ref = f"{db.PROJECT}.{db.DATASET}"
        try:
            self.client.get_dataset(dataset_ref)
            return
        except Exception:
            logger.info("Dataset %s not found, creating it.", dataset_ref)
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        try:
            self.client.create_dataset(dataset, timeout=30)
        except Exception:
            logger.exception("Failed to create BigQuery dataset %s", dataset_ref)
            raise

    def _get_full_table_id(self, table_name):
        return db.qualified_name(table_name)

    def get_last_date(self, table_name, date_column, filter_column=None, filter_value=None):
        """Fetches the latest date from a specific table and column, optionally filtering by another column."""
        full_table_id = self._get_full_table_id(table_name)

        query = f"SELECT {date_column} FROM `{full_table_id}`"
        job_config = bigquery.QueryJobConfig()
        if filter_column and filter_value:
            query += f" WHERE {filter_column} = @filter_val"
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter("filter_val", "STRING", filter_value)
            ]
        query += f" ORDER BY {date_column} DESC LIMIT 1"

        try:
            for row in self.client.query(query, job_config=job_config).result():
                return str(row[date_column])
            return None
        except Exception as e:
            logger.warning("Error fetching last date from %s: %s", full_table_id, e)
            return None

    def upload_dataframe(self, df, table_name, chunk_size=None, truncate=False):
        """Uploads a pandas DataFrame to a BigQuery table."""
        if df.empty:
            return

        df['updated_at'] = pd.Timestamp.utcnow()
        # BigQuery column names allow only alphanumerics and underscores.
        df.columns = [re.sub(r'[^a-zA-Z0-9_]', '_', col) for col in df.columns]

        full_table_id = self._get_full_table_id(table_name)
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE if truncate
            else bigquery.WriteDisposition.WRITE_APPEND
        )
        if not truncate:
            job_config.schema_update_options = [bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]

        logger.info("Uploading %d records to BigQuery %s...", len(df), full_table_id)
        try:
            job = self.client.load_table_from_dataframe(df, full_table_id, job_config=job_config)
            job.result()
            logger.info("Loaded %d rows into %s.", len(df), full_table_id)
        except Exception:
            logger.exception("Error uploading to %s", full_table_id)
            raise
