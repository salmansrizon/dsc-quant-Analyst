import os
import uuid
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

PROJECT = os.environ.get("BIGQUERY_PROJECT_ID") or "dbt-test-420614"
DATASET = os.environ.get("BIGQUERY_DATASET_ID") or "lankabd_dataset"

bq = bigquery.Client(project=PROJECT)

def _full_id(table: str) -> str:
    return f"`{PROJECT}.{DATASET}.{table}`"


def _insert_rows(table: str, rows: list[dict]):
    """Insert rows via load job (free tier eligible)."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    full = f"{PROJECT}.{DATASET}.{table}"
    job = bq.load_table_from_dataframe(
        df, full,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
        )
    )
    job.result()


# ── Market Data ──────────────────────────────────────────────────────────────



def list_stocks(sector: str = None, search: str = None, limit: int = 500):
    wheres = []
    if sector:
        wheres.append("Sector = @sector")
    if search:
        wheres.append("LOWER(Symbol) LIKE @search")
    where = " AND ".join(wheres) if wheres else "TRUE"
    params = [
        bigquery.ScalarQueryParameter("sector", "STRING", sector) if sector else None,
        bigquery.ScalarQueryParameter("search", "STRING", f"%{search.lower()}%") if search else None,
    ]
    params = [p for p in params if p is not None]

    sql = f"""
        SELECT Symbol, Sector, LTP, Open, High, Low, Close, YCP,
               ROUND(Change, 2) AS Change, ROUND(__Change, 2) AS ChangePct,
               Volume_Qty_, Value_Turnover_, EPS
        FROM {_full_id('lankabd_datamatrix')}
        WHERE {where}
        ORDER BY Symbol
        LIMIT {int(limit)}
    """
    job = bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    return [dict(r) for r in job.result()]


def get_stock(symbol: str):
    sql = f"""
        SELECT Symbol, Sector, LTP, Open, High, Low, Close, YCP,
               ROUND(Change, 2) AS Change, ROUND(__Change, 2) AS ChangePct,
               Volume_Qty_, Value_Turnover_, EPS
        FROM {_full_id('lankabd_datamatrix')}
        WHERE Symbol = @symbol
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper())]
    rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
    return dict(rows[0]) if rows else None


def top_movers(limit: int = 10):
    sql = f"""
        SELECT Symbol, Sector, LTP, ROUND(__Change, 2) AS ChangePct
        FROM {_full_id('lankabd_datamatrix')}
        ORDER BY __Change DESC
        LIMIT {int(limit)}
    """
    gainers = [dict(r) for r in bq.query(sql).result()]

    sql = f"""
        SELECT Symbol, Sector, LTP, ROUND(__Change, 2) AS ChangePct
        FROM {_full_id('lankabd_datamatrix')}
        ORDER BY __Change ASC
        LIMIT {int(limit)}
    """
    losers = [dict(r) for r in bq.query(sql).result()]

    return {"gainers": gainers, "losers": losers}


def price_history(symbol: str, days: int = 365):
    sql = f"""
        SELECT Date, Symbol, LTP, High, Low, OPENP_ AS Open, Close, YCP,
               ROUND(Change__, 2) AS ChangePct, Volume_Qty_ AS Volume,
               SMA_20, RSI
        FROM {_full_id('lankabd_price_archive')}
        WHERE Symbol = @symbol
        ORDER BY Date DESC
        LIMIT {int(days)}
    """
    params = [bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper())]
    return [dict(r) for r in bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]


def list_announcements(symbol: str = None, limit: int = 50):
    wheres = []
    params = []
    if symbol:
        wheres.append("Symbol = @symbol")
        params.append(bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper()))

    where = " AND ".join(wheres) if wheres else "TRUE"
    sql = f"""
        SELECT Symbol, Date, Announcement_Type, Details, Sentiment,
               Expected_Price_Impact, Importance, Sector
        FROM {_full_id('lankabd_announcements')}
        WHERE {where}
        ORDER BY Date DESC
        LIMIT {int(limit)}
    """
    return [dict(r) for r in bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]


# ── Watchlists ───────────────────────────────────────────────────────────────

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
    return [dict(r) for r in bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]


def add_to_watchlist(user_id: str, symbol: str):
    wid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    _insert_rows("watchlists", [{
        "id": wid,
        "user_id": user_id,
        "symbol": symbol.upper(),
        "added_at": now,
        "is_deleted": False,
        "updated_at": now,
    }])
    return {"id": wid, "symbol": symbol.upper()}


# ── Portfolios ───────────────────────────────────────────────────────────────

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
    return [dict(r) for r in bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]


def add_to_portfolio(user_id: str, data: dict):
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    _insert_rows("portfolios", [{
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
    rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
    return dict(rows[0]) if rows else {}


# ── Price Alerts ─────────────────────────────────────────────────────────────

def get_alerts(user_id: str):
    sql = f"""
        SELECT a.id, a.symbol, a.target_price, a.direction,
               a.is_triggered, a.triggered_at, a.created_at,
               d.LTP AS current_price
        FROM {_full_id('price_alerts')} a
        LEFT JOIN {_full_id('lankabd_datamatrix')} d ON a.symbol = d.Symbol
        WHERE a.user_id = @uid
        ORDER BY a.created_at DESC
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    return [dict(r) for r in bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]


def create_alert(user_id: str, data: dict):
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    _insert_rows("price_alerts", [{
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



# ── Market Summary ───────────────────────────────────────────────────────────

# ── Subscriptions ────────────────────────────────────────────────────────────

def create_subscription(user_id: str, data: dict) -> dict:
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    row = {
        "id": sid,
        "user_id": user_id,
        "medium": data["medium"],
        "alert_channel": data["alert_channel"],
        "digest_channel": data["digest_channel"],
        "alert_cap": data["alert_cap"],
        "digest_cadence": data["digest_cadence"],
        "status": "pending",
        "transaction_id": None,
        "submitted_at": None,
        "decided_at": None,
        "decided_by": None,
        "created_at": now,
    }
    _insert_rows("subscription_packages", [row])
    return {"id": sid, "status": "pending", "user_id": user_id}


def get_subscription(subscription_id: str) -> dict | None:
    sql = f"""
        SELECT * FROM {_full_id('subscription_packages')}
        WHERE id = @sid LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("sid", "STRING", subscription_id)]
    rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
    return dict(rows[0]) if rows else None


def attach_transaction_id(subscription_id: str, transaction_id: str) -> dict:
    now = datetime.now(timezone.utc)
    sql = f"""
        UPDATE {_full_id('subscription_packages')}
        SET transaction_id = @txn, submitted_at = @now
        WHERE id = @sid
    """
    params = [
        bigquery.ScalarQueryParameter("txn", "STRING", transaction_id),
        bigquery.ScalarQueryParameter("now", "TIMESTAMP", now),
        bigquery.ScalarQueryParameter("sid", "STRING", subscription_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    return {"id": subscription_id, "transaction_id": transaction_id, "status": "pending"}


def decide_subscription(subscription_id: str, admin_id: str, approved: bool) -> dict:
    now = datetime.now(timezone.utc)
    new_status = "active" if approved else "rejected"
    sql = f"""
        UPDATE {_full_id('subscription_packages')}
        SET status = @status, decided_at = @now, decided_by = @admin
        WHERE id = @sid
    """
    params = [
        bigquery.ScalarQueryParameter("status", "STRING", new_status),
        bigquery.ScalarQueryParameter("now", "TIMESTAMP", now),
        bigquery.ScalarQueryParameter("admin", "STRING", admin_id),
        bigquery.ScalarQueryParameter("sid", "STRING", subscription_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    return {"id": subscription_id, "status": new_status}


def list_subscriptions() -> list[dict]:
    sql = f"""
        SELECT * FROM {_full_id('subscription_packages')}
        ORDER BY created_at DESC
    """
    return [dict(r) for r in bq.query(sql).result()]


def get_pricing() -> dict:
    weights_sql = f"SELECT * FROM {_full_id('pricing_weights')}"
    bundles_sql = f"SELECT * FROM {_full_id('admin_bundles')} WHERE is_active = TRUE"
    weights = [dict(r) for r in bq.query(weights_sql).result()]
    bundles = [dict(r) for r in bq.query(bundles_sql).result()]
    return {"weights": weights, "bundles": bundles}


def market_summary():
    sql = f"""
        SELECT total_stocks, total_sectors, avg_price, total_turnover, last_updated
        FROM {_full_id('lankabd_market_summary_cache')}
        LIMIT 1
    """
    rows = list(bq.query(sql).result())
    return dict(rows[0]) if rows else {}


def list_sectors():
    sql = f"""
        SELECT Sector, stock_count, avg_ltp, avg_change, total_volume, total_turnover
        FROM {_full_id('lankabd_sectors_cache')}
        ORDER BY Sector
    """
    return [dict(r) for r in bq.query(sql).result()]


# ── Notification Preferences ──────────────────────────────────────────────────

def get_notification_preferences(user_id: str) -> dict:
    sql = f"""
        SELECT telegram_chat_id, whatsapp_number, email,
               web_push_subscription, channels_enabled
        FROM {_full_id('notification_preferences')}
        WHERE user_id = @uid LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
    if rows:
        row = dict(rows[0])
        if isinstance(row.get("channels_enabled"), str):
            import json
            row["channels_enabled"] = json.loads(row["channels_enabled"])
        return row
    return {
        "telegram_chat_id": None,
        "whatsapp_number": None,
        "email": None,
        "web_push_subscription": None,
        "channels_enabled": [],
    }


def update_notification_preferences(user_id: str, data: dict) -> dict:
    import json
    channels = json.dumps(data.get("channels_enabled", []))
    now = datetime.now(timezone.utc)
    rows_exist = list(bq.query(
        f"SELECT user_id FROM {_full_id('notification_preferences')} WHERE user_id = @uid LIMIT 1",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
        ])
    ).result())
    if rows_exist:
        sql = f"""
            UPDATE {_full_id('notification_preferences')}
            SET telegram_chat_id = @tg, whatsapp_number = @wa, email = @em,
                web_push_subscription = @wp, channels_enabled = @ch, updated_at = @now
            WHERE user_id = @uid
        """
    else:
        _insert_rows("notification_preferences", [{
            "user_id": user_id,
            "telegram_chat_id": data.get("telegram_chat_id"),
            "whatsapp_number": data.get("whatsapp_number"),
            "email": data.get("email"),
            "web_push_subscription": data.get("web_push_subscription"),
            "channels_enabled": channels,
            "updated_at": now,
        }])
        return {**data, "channels_enabled": data.get("channels_enabled", [])}

    params = [
        bigquery.ScalarQueryParameter("tg", "STRING", data.get("telegram_chat_id")),
        bigquery.ScalarQueryParameter("wa", "STRING", data.get("whatsapp_number")),
        bigquery.ScalarQueryParameter("em", "STRING", data.get("email")),
        bigquery.ScalarQueryParameter("wp", "STRING", data.get("web_push_subscription")),
        bigquery.ScalarQueryParameter("ch", "STRING", channels),
        bigquery.ScalarQueryParameter("now", "TIMESTAMP", now),
        bigquery.ScalarQueryParameter("uid", "STRING", user_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    return {**data, "channels_enabled": data.get("channels_enabled", [])}