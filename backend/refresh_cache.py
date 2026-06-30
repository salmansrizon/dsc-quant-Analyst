import os
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

PROJECT = os.environ.get("BIGQUERY_PROJECT_ID") or "dbt-test-420614"
DATASET = os.environ.get("BIGQUERY_DATASET_ID") or "lankabd_dataset"

bq = bigquery.Client(project=PROJECT)


def _run(sql: str, label: str):
    print(f"Refreshing {label} ...", flush=True)
    bq.query(sql).result()
    print(f"  done", flush=True)


def refresh_summary_cache():
    _run(f"""
        CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.lankabd_market_summary_cache` AS
        SELECT
            COUNT(*)                        AS total_stocks,
            COUNT(DISTINCT Sector)          AS total_sectors,
            ROUND(AVG(LTP), 2)              AS avg_price,
            ROUND(SUM(Value_Turnover_), 2)  AS total_turnover,
            MAX(updated_at)                 AS last_updated
        FROM `{PROJECT}.{DATASET}.lankabd_datamatrix`
    """, "lankabd_market_summary_cache")


def refresh_sectors_cache():
    _run(f"""
        CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.lankabd_sectors_cache` AS
        SELECT
            Sector,
            COUNT(*)                        AS stock_count,
            ROUND(AVG(LTP), 2)              AS avg_ltp,
            ROUND(AVG(__Change), 2)          AS avg_change,
            SUM(Volume_Qty_)                AS total_volume,
            ROUND(SUM(Value_Turnover_), 2)  AS total_turnover
        FROM `{PROJECT}.{DATASET}.lankabd_datamatrix`
        WHERE Sector IS NOT NULL AND Sector != ''
        GROUP BY Sector
        ORDER BY Sector
    """, "lankabd_sectors_cache")


if __name__ == "__main__":
    refresh_summary_cache()
    refresh_sectors_cache()
    print("Cache refresh complete.")
