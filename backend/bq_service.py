import os
import uuid
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from dotenv import load_dotenv
from .utils import bigquery_helper  # noqa: F401 — bootstraps GOOGLE_APPLICATION_CREDENTIALS from GCP_SERVICE_ACCOUNT_JSON
from itertools import groupby
from .indicators import add_emas, compute_macd, compute_stochastic

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


def _replace_table(table: str, rows: list[dict]):
    """Rewrite a full table via load job (free tier eligible) — used in place of
    a DML UPDATE, which requires a billing account on the BigQuery project."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    full = f"{PROJECT}.{DATASET}.{table}"
    job = bq.load_table_from_dataframe(
        df, full,
        job_config=bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
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
               Volume_Qty_, Value_Turnover_, EPS,
               Audited_PE, Forward_PE, Director_Holdings, NAV_Quarter_End_
        FROM {_full_id('lankabd_datamatrix')}
        WHERE Symbol = @symbol
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper())]
    rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
    return dict(rows[0]) if rows else None


_LEADERBOARD_COLUMNS = {
    "value": ("Value_Turnover_", "DESC"),
    "gainer": ("__Change", "DESC"),
    "loser": ("__Change", "ASC"),
    "volume": ("Volume_Qty_", "DESC"),
}


def leaderboard(metric: str, limit: int = 10):
    if metric == "trade":
        return top_trade(limit)
    column, direction = _LEADERBOARD_COLUMNS[metric]
    sql = f"""
        SELECT Symbol, Sector, LTP, ROUND(__Change, 2) AS ChangePct,
               Volume_Qty_ AS Volume, Value_Turnover_ AS Value
        FROM {_full_id('lankabd_datamatrix')}
        ORDER BY {column} {direction}
        LIMIT {int(limit)}
    """
    return [dict(r) for r in bq.query(sql).result()]


def top_trade(limit: int = 10):
    sql = f"""
        WITH latest_trade AS (
            SELECT Symbol, Trade FROM (
                SELECT Symbol, SAFE_CAST(Trade AS INT64) AS Trade,
                       ROW_NUMBER() OVER (PARTITION BY Symbol ORDER BY Date DESC) AS rn
                FROM {_full_id('lankabd_price_archive')}
                WHERE SAFE_CAST(Trade AS INT64) IS NOT NULL
            )
            WHERE rn = 1
        )
        SELECT d.Symbol, d.Sector, d.LTP, ROUND(d.__Change, 2) AS ChangePct,
               d.Volume_Qty_ AS Volume, d.Value_Turnover_ AS Value, lt.Trade
        FROM {_full_id('lankabd_datamatrix')} d
        JOIN latest_trade lt ON d.Symbol = lt.Symbol
        ORDER BY lt.Trade DESC
        LIMIT {int(limit)}
    """
    return [dict(r) for r in bq.query(sql).result()]


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
    rows = [dict(r) for r in bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]
    rows.reverse()  # chronological ascending — required by add_emas, and natural for charting
    return add_emas(rows)


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
        "bundle_id": data.get("bundle_id"),
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


def create_bundle(admin_id: str, data: dict) -> dict:
    bid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    row = {
        "id": bid,
        "name": data["name"],
        "medium": data["medium"],
        "alert_channel": data["alert_channel"],
        "digest_channel": data["digest_channel"],
        "alert_cap": data["alert_cap"],
        "digest_cadence": data["digest_cadence"],
        "price": data["price"],
        "is_active": True,
        "created_at": now,
        "created_by": admin_id,
    }
    _insert_rows("admin_bundles", [row])
    return row


def update_bundle(bundle_id: str, data: dict) -> dict:
    rows = [dict(r) for r in bq.query(f"SELECT * FROM {_full_id('admin_bundles')}").result()]
    for row in rows:
        if row["id"] == bundle_id:
            row.update({
                "name": data["name"], "medium": data["medium"],
                "alert_channel": data["alert_channel"], "digest_channel": data["digest_channel"],
                "alert_cap": data["alert_cap"], "digest_cadence": data["digest_cadence"],
                "price": data["price"],
            })
            break
    _replace_table("admin_bundles", rows)
    return {"id": bundle_id, **data}


def list_bundles() -> list[dict]:
    sql = f"""
        SELECT * FROM {_full_id('admin_bundles')}
        ORDER BY created_at DESC
    """
    return [dict(r) for r in bq.query(sql).result()]


def deactivate_bundle(bundle_id: str) -> dict:
    rows = [dict(r) for r in bq.query(f"SELECT * FROM {_full_id('admin_bundles')}").result()]
    for row in rows:
        if row["id"] == bundle_id:
            row["is_active"] = False
            break
    _replace_table("admin_bundles", rows)
    return {"id": bundle_id, "is_active": False}


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


_EXTREMES_COLUMNS = {
    "pe_low": ("Audited_PE", "ASC"),
    "pe_high": ("Audited_PE", "DESC"),
    "director_holding_low": ("Director_Holdings", "ASC"),
    "director_holding_high": ("Director_Holdings", "DESC"),
}


def extremes_leaderboard(metric: str, limit: int = 10):
    if metric in ("nav_price_low", "nav_price_high"):
        direction = "ASC" if metric == "nav_price_low" else "DESC"
        sql = f"""
            SELECT Symbol, Sector, LTP,
                   ROUND(SAFE_DIVIDE(NAV_Quarter_End_, LTP), 2) AS MetricValue
            FROM {_full_id('lankabd_datamatrix')}
            WHERE NAV_Quarter_End_ IS NOT NULL AND LTP IS NOT NULL AND LTP != 0
            ORDER BY MetricValue {direction}
            LIMIT {int(limit)}
        """
        return [dict(r) for r in bq.query(sql).result()]
    column, direction = _EXTREMES_COLUMNS[metric]
    sql = f"""
        SELECT Symbol, Sector, LTP, {column} AS MetricValue
        FROM {_full_id('lankabd_datamatrix')}
        WHERE {column} IS NOT NULL
        ORDER BY {column} {direction}
        LIMIT {int(limit)}
    """
    return [dict(r) for r in bq.query(sql).result()]


def market_strength():
    sql = f"""
        SELECT
            COUNTIF(__Change > 0) AS Gainers,
            COUNTIF(__Change < 0) AS Losers,
            COUNTIF(__Change = 0) AS Unchanged
        FROM {_full_id('lankabd_datamatrix')}
    """
    rows = list(bq.query(sql).result())
    return dict(rows[0]) if rows else {}


def sector_breakdown():
    sql = f"""
        SELECT
            Sector,
            ROUND(AVG(Audited_PE), 2) AS AvgPE,
            ROUND(SUM(Value_Turnover_), 2) AS TotalTradeValue,
            COUNTIF(__Change > 0) AS GainersCount,
            COUNTIF(__Change < 0) AS LosersCount,
            ROUND(AVG(__Change), 2) AS AvgChange
        FROM {_full_id('lankabd_datamatrix')}
        WHERE Sector IS NOT NULL AND Sector != ''
        GROUP BY Sector
        ORDER BY Sector
    """
    return [dict(r) for r in bq.query(sql).result()]


_TECHNICAL_COMPUTED_METRICS = {
    "macd_low": ("macd", "ASC"),
    "macd_high": ("macd", "DESC"),
    "stochastic_low": ("stochastic", "ASC"),
    "stochastic_high": ("stochastic", "DESC"),
}


def technical_extremes(metric: str, limit: int = 10):
    if metric in ("rsi_low", "rsi_high"):
        direction = "ASC" if metric == "rsi_low" else "DESC"
        sql = f"""
            SELECT Symbol, Sector, LTP, RSI_14_ AS MetricValue
            FROM {_full_id('lankabd_datamatrix')}
            WHERE RSI_14_ IS NOT NULL
            ORDER BY RSI_14_ {direction}
            LIMIT {int(limit)}
        """
        return [dict(r) for r in bq.query(sql).result()]

    indicator, direction = _TECHNICAL_COMPUTED_METRICS[metric]
    sql = f"""
        WITH ranked AS (
            SELECT Symbol, Sector, Date, High, Low, Close, LTP,
                   ROW_NUMBER() OVER (PARTITION BY Symbol ORDER BY Date DESC) AS rn
            FROM {_full_id('lankabd_price_archive')}
            WHERE Close IS NOT NULL AND High IS NOT NULL AND Low IS NOT NULL
        )
        SELECT Symbol, Sector, Date, High, Low, Close, LTP
        FROM ranked
        WHERE rn <= 50
        ORDER BY Symbol, Date ASC
    """
    rows = [dict(r) for r in bq.query(sql).result()]

    results = []
    for symbol, group_iter in groupby(rows, key=lambda r: r["Symbol"]):
        group = list(group_iter)
        closes = [r["Close"] for r in group]
        if indicator == "macd":
            values = compute_macd(closes)
        else:
            highs = [r["High"] for r in group]
            lows = [r["Low"] for r in group]
            values = compute_stochastic(highs, lows, closes)
        latest = next((v for v in reversed(values) if v is not None), None)
        if latest is None:
            continue
        last_row = group[-1]
        results.append({
            "Symbol": symbol,
            "Sector": last_row["Sector"],
            "LTP": last_row["LTP"],
            "MetricValue": round(latest, 2),
        })

    results.sort(key=lambda r: r["MetricValue"], reverse=(direction == "DESC"))
    return results[:limit]


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