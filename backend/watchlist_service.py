"""Watchlist queries + mutations (split from the bq_service god module, #43).

Append-only: mutations record a new version rather than editing in place, and
reads go through the `watchlists_current` view. See db.append_version (#52) —
BigQuery's free tier forbids DML outright.
"""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db


def get_watchlist(user_id: str):
    sql = f"""
        SELECT w.id, w.symbol, w.added_at,
               d.LTP, d.__Change AS ChangePct, d.Sector
        FROM {db.current_view('watchlists')} w
        LEFT JOIN {db.table_id('lankabd_datamatrix')} d ON w.symbol = d.Symbol
        WHERE w.user_id = @uid
        ORDER BY w.added_at DESC
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    return db.query_rows(sql, params)


def _find_entry(user_id: str, symbol: str) -> dict | None:
    """The user's current row for a symbol, or None."""
    rows = db.query_rows(
        f"""
        SELECT id, user_id, symbol, added_at
        FROM {db.current_view('watchlists')}
        WHERE user_id = @uid AND symbol = @symbol
        LIMIT 1
        """,
        [
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
            bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper()),
        ],
    )
    return rows[0] if rows else None


def add_to_watchlist(user_id: str, symbol: str):
    symbol = symbol.upper()
    existing = _find_entry(user_id, symbol)
    if existing:
        # Already watching it — adding twice must not create a second version.
        return {"id": existing["id"], "symbol": symbol}

    wid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.append_version("watchlists", [{
        "id": wid,
        "user_id": user_id,
        "symbol": symbol,
        "added_at": now,
        "is_deleted": False,
        "updated_at": now,
    }])
    return {"id": wid, "symbol": symbol}


def remove_from_watchlist(user_id: str, symbol: str) -> bool:
    """Tombstone the user's entry. Returns whether one was being watched."""
    entry = _find_entry(user_id, symbol)
    if not entry:
        return False

    db.append_version("watchlists", [{
        **entry,
        "is_deleted": True,
        "updated_at": datetime.now(timezone.utc),
    }])
    return True
