"""Portfolio queries + mutations (split from the bq_service god module, #43).

Append-only: mutations record a new version rather than editing in place, and
reads go through the `portfolios_current` view. See db.append_version (#52) —
BigQuery's free tier forbids DML outright.
"""
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from . import db


# Whitelist of updatable portfolio columns. Anything else a caller sends (id,
# user_id, is_deleted, created_at) is ignored rather than written.
_PORTFOLIO_UPDATE_FIELDS = frozenset({
    "buy_price", "quantity", "price_target", "stop_loss", "notes",
})


def get_portfolio(user_id: str):
    sql = f"""
        SELECT p.id, p.symbol, p.buy_price, p.quantity, p.buy_date,
               p.price_target, p.stop_loss, p.notes,
               d.LTP AS current_price,
               ROUND((d.LTP - p.buy_price) * p.quantity, 2) AS pnl,
               ROUND(((d.LTP - p.buy_price) / p.buy_price) * 100, 2) AS pnl_percent
        FROM {db.current_view('portfolios')} p
        {db.price_join('p')}
        WHERE p.user_id = @uid
        ORDER BY p.created_at DESC
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    return db.query_rows(sql, params)


def _find_holding(portfolio_id: str, user_id: str) -> dict | None:
    """One of the user's current holdings, or None.

    Scoped by owner: guessing an id must never reach someone else's holding.
    """
    return db.find_current("portfolios", id=portfolio_id, user_id=user_id)


def add_to_portfolio(user_id: str, data: dict):
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.append_version("portfolios", [{
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


def update_portfolio(portfolio_id: str, user_id: str, data: dict) -> bool:
    """Append an updated version of the holding. Returns whether it changed.

    Read-modify-append: the whole merged row is written, so the version log
    always holds complete rows. Concurrent edits to the *same* holding are
    last-writer-wins; edits to different rows never interfere, which is the
    property the old whole-table rewrite lacked (#40).
    """
    changes = {k: v for k, v in data.items() if k in _PORTFOLIO_UPDATE_FIELDS and v is not None}
    if not changes:
        return False

    # Scoped by owner (id + user_id) so guessing an id can't reach another
    # user's holding; db.revise reads-merges-appends the whole row (#70).
    return db.revise("portfolios", changes, id=portfolio_id, user_id=user_id)


def delete_portfolio(portfolio_id: str, user_id: str) -> bool:
    """Tombstone one of the user's holdings. Returns whether it existed."""
    holding = _find_holding(portfolio_id, user_id)
    if not holding:
        return False

    db.tombstone("portfolios", holding)
    return True


def portfolio_summary(user_id: str):
    sql = f"""
        SELECT COUNT(*) AS total_holdings,
               ROUND(SUM(p.buy_price * p.quantity), 2) AS total_invested,
               ROUND(SUM(d.LTP * p.quantity), 2) AS current_value,
               ROUND(SUM((d.LTP - p.buy_price) * p.quantity), 2) AS total_pnl,
               ROUND(AVG(((d.LTP - p.buy_price) / p.buy_price) * 100), 2) AS avg_pnl_pct
        FROM {db.current_view('portfolios')} p
        {db.price_join('p')}
        WHERE p.user_id = @uid
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    rows = db.query_rows(sql, params)
    return rows[0] if rows else {}
