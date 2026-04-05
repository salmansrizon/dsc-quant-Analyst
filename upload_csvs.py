import os
import pandas as pd
import numpy as np
from supabase import create_client, Client

from dotenv import load_dotenv

# Load local environment variables from .env file
load_dotenv()

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_csv(file_path, table_name, chunk_size=500, truncate=False):
    print(f"Uploading {file_path} to {table_name}...")
    if not os.path.exists(file_path):
        print(f"File {file_path} not found. Skipping.")
        return

    if truncate:
        print(f"  Truncating {table_name}...")
        try:
            supabase.table(table_name).delete().neq("Symbol", "STAY_SAFE_DUMMY").execute()
        except Exception as e:
            print(f"  Warning during truncation: {e}")

    # Load data
    df = pd.read_csv(file_path)
    
    # Drop any leftover unnamed or empty string columns
    df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed|^$', case=False, na=False)]
    
    # Pre-cleaning: Replace placeholders like '-' with actual None for SQL compat
    df = df.replace(['-', 'N/A', 'n/a', 'nan', 'inf', '-inf'], np.nan)
    
    # Force convert to object type to allow Python 'None' to persist (Json compatible for SQL Null)
    df = df.replace([np.nan], [None]).astype(object)
    df = df.where(pd.notnull(df), None)
    
    # Convert to list of dicts
    records = df.to_dict(orient='records')
    
    # Upload in chunks
    total = len(records)
    for i in range(0, total, chunk_size):
        chunk = records[i:i + chunk_size]
        try:
            supabase.table(table_name).insert(chunk).execute()
            if (i + chunk_size) % 5000 == 0 or (i + chunk_size) >= total:
                print(f"  Inserted {min(i + chunk_size, total)}/{total} records.")
        except Exception as e:
            print(f"  Error inserting chunk starting at {i}: {e}")

if __name__ == "__main__":
    # 1. Datamatrix (Small)
    upload_csv('sample/lankabd_data_all_sectors.csv', 'lankabd_datamatrix', truncate=True)
    
    # 2. Announcements (Medium)
    upload_csv('sample/dse_announcements.csv', 'lankabd_announcements', truncate=True)
    
    # 3. Historical Prices (Large)
    upload_csv('sample/dse_historical_prices.csv', 'lankabd_price_archive', truncate=True)

    print("Success: All uploads completed.")
