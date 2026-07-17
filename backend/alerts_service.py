"""Price-alert queries + mutations (split from the bq_service god module, #43)."""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db


def get_alerts(user_id: str):
    sql = f"""
        SELECT a.id, a.symbol, a.target_price, a.direction,
               a.is_triggered, a.triggered_at, a.created_at,
               d.LTP AS current_price
        FROM {db.table_id('price_alerts')} a
        LEFT JOIN {db.table_id('lankabd_datamatrix')} d ON a.symbol = d.Symbol
        WHERE a.user_id = @uid
        ORDER BY a.created_at DESC
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    return db.query_rows(sql, params)


def create_alert(user_id: str, data: dict):
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.insert_rows("price_alerts", [{
        "id": aid,
        "user_id": user_id,
        "symbol": data["symbol"].upper(),
        "target_price": data["target_price"],
        "direction": data["direction"],
        "is_triggered": False,
        "triggered_at": None,
        "created_at": now,
    }])
    return {"id": aid, "symbol": data["symbol"].upper()}


def delete_alert(alert_id: str, user_id: str):
    db.execute_dml(
        f"DELETE FROM {db.table_id('price_alerts')} WHERE id = @id AND user_id = @uid",
        [
            bigquery.ScalarQueryParameter("id", "STRING", alert_id),
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
        ],
    )
    return True
