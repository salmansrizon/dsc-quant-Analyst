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
            print(f"Dataset {dataset_ref} not found. Creating...")
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
            print(f"Error fetching last date from {full_table_id}: {e}")
            return None

    def upload_dataframe(self, df, table_name, truncate=False):
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

        # load_table_from_json, not load_table_from_dataframe: the dataframe path
        # requires pyarrow (~500MB), which is deliberately excluded from
        # requirements.txt because it blew the Vercel bundle past its 500MB limit
        # (same reason db.insert_rows uses the JSON path). It "worked" locally
        # only because a dev machine happens to have pyarrow; CI does not, so the
        # scheduled ETL failed with "requires pyarrow to be installed". Serialize
        # to JSON-safe records: NaN -> None (not valid JSON), Timestamp -> ISO.
        safe = df.astype(object).where(pd.notnull(df), None)
        rows = [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in rec.items()}
            for rec in safe.to_dict("records")
        ]

        print(f"Uploading {len(df)} records to BigQuery {full_table_id}...")
        try:
            job = self.client.load_table_from_json(rows, full_table_id, job_config=job_config)
            job.result()
            print(f"  Successfully loaded {len(df)} rows into {full_table_id}.")
        except Exception as e:
            logger.exception("Error uploading to %s", full_table_id)
            print(f"  Error uploading to {full_table_id}: {e}")
            raise
