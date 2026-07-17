"""Portfolio queries + mutations (split from the bq_service god module, #43)."""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db

_full_id = db.table_id

# Whitelist of updatable portfolio columns and their BigQuery param types.
_PORTFOLIO_UPDATE_TYPES = {
    "buy_price": "FLOAT64",
    "quantity": "INT64",
    "price_target": "FLOAT64",
    "stop_loss": "FLOAT64",
    "notes": "STRING",
}


def get_portfolio(user_id: str):
    sql = f"""
        SELECT p.id, p.symbol, p.buy_price, p.quantity, p.buy_date,
               p.price_target, p.stop_loss, p.notes,
               d.LTP AS current_price,
               ROUND((d.LTP - p.buy_price) * p.quantity, 2) AS pnl,
               ROUND(((d.LTP - p.buy_price) / p.buy_price) * 100, 2) AS pnl_percent
        FROM {_full_id('portfolios')} p
        LEFT JOIN {_full_id('lankabd_datamatrix')} d ON p.symbol = d.Symbol
        WHERE p.user_id = @uid AND p.is_deleted = FALSE
        ORDER BY p.created_at DESC
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    return db.query_rows(sql, params)


def add_to_portfolio(user_id: str, data: dict):
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.insert_rows("portfolios", [{
        "id": pid,
        "user_id": user_id,
        "symbol": data["symbol"].upper(),
        "buy_price": data["buy_price"],
        "quantity": data["quantity"],
        "buy_date": data.get("buy_date", ""),
        "price_target": data.get("price_target", 0.0) or 0.0,
        "stop_loss": data.get("stop_loss", 0.0) or 0.0,
        "notes": data.get("notes", ""),
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }])
    return {"id": pid, "symbol": data["symbol"].upper()}


def update_portfolio(portfolio_id: str, user_id: str, data: dict):
    updates = {k: v for k, v in data.items() if k in _PORTFOLIO_UPDATE_TYPES and v is not None}
    if not updates:
        return False

    set_clauses = ["updated_at = @now"]
    params = [
        bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc)),
        bigquery.ScalarQueryParameter("id", "STRING", portfolio_id),
        bigquery.ScalarQueryParameter("uid", "STRING", user_id),
    ]
    for col, val in updates.items():
        set_clauses.append(f"{col} = @{col}")
        params.append(bigquery.ScalarQueryParameter(col, _PORTFOLIO_UPDATE_TYPES[col], val))

    affected = db.execute_dml(
        f"""
        UPDATE {_full_id('portfolios')}
        SET {', '.join(set_clauses)}
        WHERE id = @id AND user_id = @uid AND is_deleted = FALSE
        """,
        params,
    )
    return affected > 0


def delete_portfolio(portfolio_id: str, user_id: str):
    db.execute_dml(
        f"""
        UPDATE {_full_id('portfolios')}
        SET is_deleted = TRUE, updated_at = @now
        WHERE id = @id AND user_id = @uid AND is_deleted = FALSE
        """,
        [
            bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc)),
            bigquery.ScalarQueryParameter("id", "STRING", portfolio_id),
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
        ],
    )
    return True


def portfolio_summary(user_id: str):
    sql = f"""
        SELECT COUNT(*) AS total_holdings,
               ROUND(SUM(p.buy_price * p.quantity), 2) AS total_invested,
               ROUND(SUM(d.LTP * p.quantity), 2) AS current_value,
               ROUND(SUM((d.LTP - p.buy_price) * p.quantity), 2) AS total_pnl,
               ROUND(AVG(((d.LTP - p.buy_price) / p.buy_price) * 100), 2) AS avg_pnl_pct
        FROM {_full_id('portfolios')} p
        LEFT JOIN {_full_id('lankabd_datamatrix')} d ON p.symbol = d.Symbol
        WHERE p.user_id = @uid AND p.is_deleted = FALSE
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    rows = db.query_rows(sql, params)
    return rows[0] if rows else {}
