"""Watchlist queries + mutations (split from the bq_service god module, #43)."""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db

_full_id = db.table_id


def get_watchlist(user_id: str):
    sql = f"""
        SELECT w.id, w.symbol, w.added_at,
               d.LTP, d.__Change AS ChangePct, d.Sector
        FROM {_full_id('watchlists')} w
        LEFT JOIN {_full_id('lankabd_datamatrix')} d ON w.symbol = d.Symbol
        WHERE w.user_id = @uid AND w.is_deleted = FALSE
        ORDER BY w.added_at DESC
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    return db.query_rows(sql, params)


def add_to_watchlist(user_id: str, symbol: str):
    wid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.insert_rows("watchlists", [{
        "id": wid,
        "user_id": user_id,
        "symbol": symbol.upper(),
        "added_at": now,
        "is_deleted": False,
        "updated_at": now,
    }])
    return {"id": wid, "symbol": symbol.upper()}


def remove_from_watchlist(user_id: str, symbol: str):
    db.execute_dml(
        f"""
        UPDATE {_full_id('watchlists')}
        SET is_deleted = TRUE, updated_at = @now
        WHERE user_id = @uid AND symbol = @symbol AND is_deleted = FALSE
        """,
        [
            bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc)),
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
            bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper()),
        ],
    )
    return True
