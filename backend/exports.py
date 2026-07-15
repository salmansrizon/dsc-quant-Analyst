"""Backend export functionality for Admin panel."""

import csv
import json
import io
from typing import List, Dict, Any
from fastapi import HTTPException
import pandas as pd
from google.cloud import bigquery


def _get_bigquery_client():
    """Initialize BigQuery client."""
    import os
    PROJECT = os.environ.get("BIGQUERY_PROJECT_ID") or "dbt-test-420614"
    return bigquery.Client(project=PROJECT)


def _list_tables() -> List[str]:
    """List all tables in the dataset."""
    client = _get_bigquery_client()
    dataset = client.dataset(os.environ.get("BIGQUERY_DATASET_ID") or "lankabd_dataset")
    return [table.name for table in dataset.tables()]


def export_announcements() -> tuple[bytes, str]:
    """Export announcements as CSV."""
    client = _get_bigquery_client()
    sql = """
        SELECT Symbol, Date, Announcement_Type, Details, LTP
        FROM `dbt-test-420614.lankabd_dataset.announcements`
        ORDER BY Date DESC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("symbol", "STRING", ""),
        ]
    )
    query = client.query(sql, job_config=job_config)
    results = [dict(r) for r in query.result()]
    
    if not results:
        raise HTTPException(status_code=404, detail="No announcements found")
    
    df = pd.DataFrame(results)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue().encode('utf-8'), 'text/csv'


def export_price_archive() -> tuple[bytes, str]:
    """Export price archive as CSV."""
    client = _get_bigquery_client()
    sql = """
        SELECT Date, Symbol, LTP, Close, Volume_Qty_
        FROM `dbt-test-420614.lankabd_dataset.price_archive`
        ORDER BY Date DESC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[]
    )
    query = client.query(sql, job_config=job_config)
    results = [dict(r) for r in query.result()]
    
    df = pd.DataFrame(results)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue().encode('utf-8'), 'text/csv'


def export_master_dataset() -> tuple[str, str]:
    """Export master dataset as JSON with full structure."""
    client = _get_bigquery_client()
    sql = """
        SELECT Symbol, LTP, Change, Sector, Volume_Qty_ 
        FROM `dbt-test-420614.lankabd_dataset.lankabd_datamatrix`
        LIMIT 1000
    """
    
    job_config = bigquery.QueryJobConfig()
    query = client.query(sql, job_config=job_config)
    results = [dict(r) for r in query.result()]
    
    return json.dumps(results, indent=4), 'application/json'


def export_table(table_name: str) -> bytes:
    """Export a specific table as CSV."""
    client = _get_bigquery_client()
    sql = f"""
        SELECT * FROM `{_get_full_table_id(table_name)}`
    """
    
    job_config = bigquery.QueryJobConfig()
    query = client.query(sql, job_config=job_config)
    results = [dict(r) for r in query.result()]
    
    df = pd.DataFrame(results)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue().encode('utf-8')


def _get_full_table_id(table_name: str) -> str:
    """Create full table ID."""
    import os
    project = os.environ.get('BIGQUERY_PROJECT_ID') or 'dbt-test-420614'
    dataset = os.environ.get('BIGQUERY_DATASET_ID') or 'lankabd_dataset'
    return f"'{project}.{dataset}.{table_name}'"