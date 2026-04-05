import os
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load local environment variables from .env file
load_dotenv()

# Configuration should be loaded from Environment Variables
# These will be set in GitHub secrets or local .env
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

class SupabaseHelper:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required.")
        self._supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self._table_schemas = {} # Cache for table column names

    def _get_table_columns(self, table_name):
        """Fetches allowed column names for a table and caches them."""
        if table_name in self._table_schemas:
            return self._table_schemas[table_name]
        
        try:
            # Fetch a single row to probe the schema
            response = self._supabase.table(table_name).select("*").limit(1).execute()
            if hasattr(response, 'data') and len(response.data) >= 0:
                # If table is empty, we still get an empty list with correct structure in metadata or similar
                # For now, we take keys from the first record if available, 
                # or we use a more robust way to probe if needed.
                # However, in PostgREST, a simple way is to check the keys of the first non-empty response.
                if len(response.data) > 0:
                    cols = list(response.data[0].keys())
                    self._table_schemas[table_name] = cols
                    return cols
                else:
                    # Fallback or empty table - we might need to handle this differently
                    # For now, if table is empty, we can't easily probe via select * unless we use a view or RPC.
                    # As a simpler fallback, we'll return None and skip filtering if we can't probe.
                    return None
        except Exception as e:
            print(f"Warning: Could not fetch schema for {table_name}: {e}")
            return None
        return None

    def get_last_date(self, table_name, date_column):
        """Fetches the latest date from a specific table and column."""
        try:
            response = self._supabase.table(table_name) \
                .select(date_column) \
                .order(date_column, desc=True) \
                .limit(1) \
                .execute()
            
            if response.data and len(response.data) > 0:
                last_date_str = response.data[0][date_column]
                # Handle cases where the date column is already a date object or string
                return last_date_str
            return None
        except Exception as e:
            print(f"Error fetching last date from {table_name}: {e}")
            return None

    def upload_dataframe(self, df, table_name, chunk_size=500, truncate=False):
        """Uploads a pandas DataFrame to a Supabase table in chunks."""
        import numpy as np
        if df.empty:
            return

        if truncate:
            print(f"  Truncating {table_name}...")
            try:
                # Standard way to clear a table in Supabase via API
                self._supabase.table(table_name).delete().neq("Symbol", "STAY_SAFE_DUMMY").execute()
            except Exception as e:
                print(f"  Warning during truncation: {e}")

        # Prepare for bulk insert: Replace NaT/NaN/Inf/Empty strings with None (SQL NULL)
        # We use as_type(object) to allow None as a separate type in the dictionary
        df = df.replace([np.inf, -np.inf, np.nan, ""], None).astype(object)
        df = df.where(pd.notnull(df), None)

        # Schema filtering: Only keep columns that belong to the table
        table_cols = self._get_table_columns(table_name)
        if table_cols:
            df_cols = df.columns.tolist()
            valid_cols = [c for c in df_cols if c in table_cols]
            dropped = [c for c in df_cols if c not in table_cols]
            if dropped:
                print(f"  Note: Dropping columns from upload that are not in schema: {dropped}")
            df = df[valid_cols]
        
        # Convert to list of dicts
        records = df.to_dict(orient='records')
        
        total = len(records)
        print(f"Uploading {total} records to {table_name}...")
        
        for i in range(0, total, chunk_size):
            chunk = records[i:i + chunk_size]
            try:
                self._supabase.table(table_name).upsert(chunk).execute()
                print(f"  Upserted {min(i + chunk_size, total)}/{total}")
            except Exception as e:
                print(f"  Error upserting chunk into {table_name}: {e}")
                # Optional: log the error and re-raise if it's fatal
                raise e
