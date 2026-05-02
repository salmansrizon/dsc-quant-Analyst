import os
import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

# Set Google Application Credentials if json file exists locally
json_path = os.path.join(os.path.dirname(__file__), 'dbt-test-420614-6c3337b4e737.json')
if os.path.exists(json_path) and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path

BIGQUERY_PROJECT_ID = os.environ.get("BIGQUERY_PROJECT_ID") or "dbt-test-420614"
BIGQUERY_DATASET_ID = os.environ.get("BIGQUERY_DATASET_ID") or "lankabd_dataset" # Default dataset

class BigQueryHelper:
    def __init__(self):
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            print("Warning: GOOGLE_APPLICATION_CREDENTIALS not set.")
        self.client = bigquery.Client(project=BIGQUERY_PROJECT_ID)
        self.dataset_id = BIGQUERY_DATASET_ID
        
        # Ensure dataset exists
        dataset_ref = f"{BIGQUERY_PROJECT_ID}.{self.dataset_id}"
        try:
            self.client.get_dataset(dataset_ref)
        except Exception:
            print(f"Dataset {dataset_ref} not found. Creating...")
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US" # Default location, can be configured
            self.client.create_dataset(dataset, timeout=30)
            print(f"Created dataset {dataset_ref}")

    def _get_full_table_id(self, table_name):
        return f"{BIGQUERY_PROJECT_ID}.{self.dataset_id}.{table_name}"

    def get_last_date(self, table_name, date_column, filter_column=None, filter_value=None):
        """Fetches the latest date from a specific table and column, optionally filtering by another column."""
        full_table_id = self._get_full_table_id(table_name)
        
        query = f"SELECT {date_column} FROM `{full_table_id}`"
        if filter_column and filter_value:
             # Sanitize or parameterize if needed, but for internal use this is ok
             query += f" WHERE {filter_column} = @filter_val"
        
        query += f" ORDER BY {date_column} DESC LIMIT 1"
        
        job_config = bigquery.QueryJobConfig()
        if filter_column and filter_value:
             job_config.query_parameters = [
                 bigquery.ScalarQueryParameter("filter_val", "STRING", filter_value)
             ]
             
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            for row in results:
                return str(row[date_column])
            return None
        except Exception as e:
            print(f"Error fetching last date from {full_table_id}: {e}")
            return None

    def upload_dataframe(self, df, table_name, chunk_size=None, truncate=False):
        """Uploads a pandas DataFrame to a BigQuery table."""
        if df.empty:
            return

        # Add updated_at timestamp
        df['updated_at'] = pd.Timestamp.utcnow()

        # Sanitize column names for BigQuery (only alphanumeric and underscores allowed)
        import re
        df.columns = [re.sub(r'[^a-zA-Z0-9_]', '_', col) for col in df.columns]

        full_table_id = self._get_full_table_id(table_name)
        
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE if truncate else bigquery.WriteDisposition.WRITE_APPEND
        )
        if not truncate:
            job_config.schema_update_options = [bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]

        print(f"Uploading {len(df)} records to BigQuery {full_table_id}...")
        try:
            job = self.client.load_table_from_dataframe(
                df, full_table_id, job_config=job_config
            )
            job.result()  # Wait for the job to complete.
            print(f"  Successfully loaded {len(df)} rows into {full_table_id}.")
        except Exception as e:
            print(f"  Error uploading to {full_table_id}: {e}")
            raise e