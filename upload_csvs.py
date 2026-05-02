import os
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from utils.bigquery_helper import BigQueryHelper

# Load local environment variables from .env file
load_dotenv()

bq = BigQueryHelper()

def upload_csv(file_path, table_name, chunk_size=500, truncate=False):
    print(f"Uploading {file_path} to {table_name}...")
    if not os.path.exists(file_path):
        print(f"File {file_path} not found. Skipping.")
        return

    # Load data
    df = pd.read_csv(file_path)
    
    # Drop any leftover unnamed or empty string columns
    df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed|^$', case=False, na=False)]
    
    # Pre-cleaning: Replace placeholders like '-' with actual None
    df = df.replace(['-', 'N/A', 'n/a', 'nan', 'inf', '-inf'], np.nan)
    
    # Upload directly via BigQuery Helper
    bq.upload_dataframe(df, table_name, truncate=truncate)

if __name__ == "__main__":
    # 1. Datamatrix (Small)
    upload_csv('sample/lankabd_data_all_sectors.csv', 'lankabd_datamatrix', truncate=True)
    
    # 2. Announcements (Medium)
    upload_csv('sample/dse_announcements.csv', 'lankabd_announcements', truncate=True)
    
    # 3. Historical Prices (Large)
    upload_csv('sample/dse_historical_prices.csv', 'lankabd_price_archive', truncate=True)

    print("Success: All uploads completed.")
