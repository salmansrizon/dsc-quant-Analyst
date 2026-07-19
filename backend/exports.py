"""Admin-panel exports: whole tables as CSV or JSON.

Reads go through db.query_rows like every other read. This module used to hold a
second read path — a client wrapper plus four hand-rolled copies of
`client.query(...)` + `[dict(r) for r in ...]` — which is what db.query_rows is.
"""
import io
import json

import pandas as pd
from fastapi import HTTPException

from . import db


def _csv(rows: list[dict]) -> tuple[bytes, str]:
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8"), "text/csv"


def export_announcements() -> tuple[bytes, str]:
    """Export announcements as CSV."""
    # The table is `lankabd_announcements`; `announcements` has never existed.
    # It carries no LTP column either — the price lives in the price archive.
    rows = db.query_rows(f"""
        SELECT Symbol, Date, Announcement_Type, Details, Sector, Importance
        FROM {db.table_id('lankabd_announcements')}
        ORDER BY Date DESC
    """)
    if not rows:
        raise HTTPException(status_code=404, detail="No announcements found")
    return _csv(rows)


def export_price_archive() -> tuple[bytes, str]:
    """Export price archive as CSV."""
    rows = db.query_rows(f"""
        SELECT Date, Symbol, LTP, Close, Volume_Qty_
        FROM {db.table_id('lankabd_price_archive')}
        ORDER BY Date DESC
    """)
    return _csv(rows)


def export_master_dataset() -> tuple[str, str]:
    """Export the datamatrix as JSON."""
    rows = db.query_rows(f"""
        SELECT Symbol, LTP, Change, Sector, Volume_Qty_
        FROM {db.table_id('lankabd_datamatrix')}
        LIMIT 1000
    """)
    return json.dumps(rows, indent=4, default=str), "application/json"
