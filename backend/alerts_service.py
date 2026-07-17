"""Price-alert queries + mutations (split from the bq_service god module, #43).

Append-only: mutations record a new version rather than editing in place, and
reads go through the `price_alerts_current` view. See db.append_version (#52) —
BigQuery's free tier forbids DML outright.
"""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db


def get_alerts(user_id: str):
    sql = f"""
        SELECT a.id, a.symbol, a.target_price, a.direction,
               a.is_triggered, a.triggered_at, a.created_at,
               d.LTP AS current_price
        FROM {db.current_view('price_alerts')} a
        LEFT JOIN {db.table_id('lankabd_datamatrix')} d ON a.symbol = d.Symbol
        WHERE a.user_id = @uid
        ORDER BY a.created_at DESC
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    return db.query_rows(sql, params)


def pending_alerts() -> list[dict]:
    """Every untriggered alert, across all users, with its symbol's current price.

    For the alert-checker batch job (#48). The join is done here rather than in
    pandas because the column names differ by case — alerts store `symbol`, the
    datamatrix stores `Symbol` — and merging on the wrong one is what made the
    checker raise KeyError before it could fire a single alert.

    COALESCE on is_triggered: NOT NULL is NULL, so an alert with a null flag
    would never be returned.
    """
    return db.query_rows(f"""
        SELECT a.id, a.user_id, a.symbol, a.target_price, a.direction,
               d.LTP AS current_price
        FROM {db.current_view('price_alerts')} a
        LEFT JOIN {db.table_id('lankabd_datamatrix')} d ON a.symbol = d.Symbol
        WHERE NOT COALESCE(a.is_triggered, FALSE)
    """)


def _find_alert(alert_id: str, user_id: str) -> dict | None:
    """One of the user's current alerts, or None.

    Scoped by owner: guessing an id must never reach someone else's alert.
    """
    return db.find_current("price_alerts", id=alert_id, user_id=user_id)


def create_alert(user_id: str, data: dict):
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.append_version("price_alerts", [{
        "id": aid,
        "user_id": user_id,
        "symbol": data["symbol"].upper(),
        "target_price": data["target_price"],
        "direction": data["direction"],
        "is_triggered": False,
        "triggered_at": None,
        "created_at": now,
        "is_deleted": False,
        "updated_at": now,
    }])
    return {"id": aid, "symbol": data["symbol"].upper()}


def delete_alert(alert_id: str, user_id: str) -> bool:
    """Tombstone one of the user's alerts. Returns whether it existed."""
    alert = _find_alert(alert_id, user_id)
    if not alert:
        return False

    db.tombstone("price_alerts", alert)
    return True


def mark_triggered(alert_ids: list[str]) -> int:
    """Record alerts as triggered. Returns how many were marked.

    For the alert-checker batch job (#48): appends a triggered version of each
    alert instead of the UPDATE the free tier forbids (#52). Already-triggered
    alerts are skipped, so a re-run cannot double-fire.
    """
    if not alert_ids:
        return 0

    now = datetime.now(timezone.utc)
    rows = db.query_rows(
        f"""
        SELECT * FROM {db.current_view('price_alerts')}
        WHERE id IN UNNEST(@ids) AND NOT COALESCE(is_triggered, FALSE)
        """,
        [bigquery.ArrayQueryParameter("ids", "STRING", alert_ids)],
    )
    if not rows:
        return 0

    db.append_version("price_alerts", [
        {**r, "is_triggered": True, "triggered_at": now, "updated_at": now}
        for r in rows
    ])
    return len(rows)
