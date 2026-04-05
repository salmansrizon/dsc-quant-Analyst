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
