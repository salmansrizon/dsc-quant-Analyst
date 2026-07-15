import os
import uuid
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from dotenv import load_dotenv

from . import indicators

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


def _execute_dml(sql: str, params: list["bigquery.ScalarQueryParameter"]) -> int:
    """Run a parameterized UPDATE/DELETE and return affected row count.

    Row-level DML replaces the old read-all + WRITE_TRUNCATE pattern, which
    replaced the whole table with one user's rows and destroyed every other
    user's data on each mutation (see ticket #40).
    """
    job = bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    job.result()
    return job.num_dml_affected_rows or 0

# ── Market Data ──────────────────────────────────────────────────────────────

def list_sectors():
    sql = f"""
        SELECT Sector,
               COUNT(*) AS stock_count,
               ROUND(AVG(LTP), 2) AS avg_ltp,
               ROUND(AVG(__Change), 2) AS avg_change,
               SUM(Volume_Qty_) AS total_volume,
               ROUND(SUM(Value_Turnover_), 2) AS total_turnover
        FROM {_full_id('lankabd_datamatrix')}
        WHERE Sector IS NOT NULL AND Sector != ''
        GROUP BY Sector
        ORDER BY Sector
    """
    return [dict(r) for r in bq.query(sql).result()]


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


def technical_indicators(symbol: str, days: int = 365):
    """Compute the v1 technical-indicator bundle (spec 4) from price history.

    Indicators are computed on-read in Python rather than stored in a
    precomputed BigQuery table — see ticket "Decide technical-indicator compute
    & storage architecture on BigQuery" (#31). This is the canonical indicator
    source; the raw SMA_20/RSI columns in lankabd_price_archive are left as
    scraped passthrough on price_history and are not reconciled here.
    """
    rows = price_history(symbol, days=days)
    if not rows:
        return {"symbol": symbol.upper(), "indicators": None, "points": 0}

    # price_history returns newest-first; indicators need oldest-first.
    rows = list(reversed(rows))

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _series(*keys):
        out = []
        for r in rows:
            val = None
            for k in keys:
                val = _num(r.get(k))
                if val is not None:
                    break
            out.append(val)
        return out

    closes = _series("Close", "LTP")
    highs = _series("High")
    lows = _series("Low")
    volumes = _series("Volume")

    # Drop rows with no usable close; keep parallel arrays aligned. Note this
    # collapses calendar gaps into adjacent bars (v1 accepts the distortion).
    clean = [(c, h, l, v) for c, h, l, v in zip(closes, highs, lows, volumes) if c is not None]
    if not clean:
        return {"symbol": symbol.upper(), "indicators": None, "points": 0}
    closes = [c for c, _, _, _ in clean]
    highs = [h if h is not None else c for c, h, _, _ in clean]
    lows = [l if l is not None else c for c, _, l, _ in clean]
    volumes = [v if v is not None else 0.0 for *_, v in clean]

    bundle = indicators.compute_all(closes, highs, lows, volumes)
    return {"symbol": symbol.upper(), "points": len(closes), "indicators": bundle}


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


def remove_from_watchlist(user_id: str, symbol: str):
    _execute_dml(
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


# Whitelist of updatable portfolio columns and their BigQuery param types.
_PORTFOLIO_UPDATE_TYPES = {
    "buy_price": "FLOAT64",
    "quantity": "INT64",
    "price_target": "FLOAT64",
    "stop_loss": "FLOAT64",
    "notes": "STRING",
}


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

    affected = _execute_dml(
        f"""
        UPDATE {_full_id('portfolios')}
        SET {', '.join(set_clauses)}
        WHERE id = @id AND user_id = @uid AND is_deleted = FALSE
        """,
        params,
    )
    return affected > 0


def delete_portfolio(portfolio_id: str, user_id: str):
    _execute_dml(
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


def delete_alert(alert_id: str, user_id: str):
    _execute_dml(
        f"DELETE FROM {_full_id('price_alerts')} WHERE id = @id AND user_id = @uid",
        [
            bigquery.ScalarQueryParameter("id", "STRING", alert_id),
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
        ],
    )
    return True


# ── Market Summary ───────────────────────────────────────────────────────────

def market_summary():
    sql = f"""
        SELECT COUNT(*) AS total_stocks,
               COUNT(DISTINCT Sector) AS total_sectors,
               ROUND(AVG(LTP), 2) AS avg_price,
               ROUND(SUM(Value_Turnover_), 2) AS total_turnover,
               MAX(updated_at) AS last_updated
        FROM {_full_id('lankabd_datamatrix')}
    """
    rows = list(bq.query(sql).result())
    return dict(rows[0]) if rows else {}