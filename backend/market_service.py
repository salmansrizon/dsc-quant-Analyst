"""Read-only market-data queries (split from the bq_service god module, #43)."""
from google.cloud import bigquery

from . import db
from . import indicators
from . import price_series


def list_sectors():
    sql = f"""
        SELECT Sector,
               COUNT(*) AS stock_count,
               ROUND(AVG(LTP), 2) AS avg_ltp,
               ROUND(AVG(__Change), 2) AS avg_change,
               SUM(Volume_Qty_) AS total_volume,
               ROUND(SUM(Value_Turnover_), 2) AS total_turnover
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE Sector IS NOT NULL AND Sector != ''
        GROUP BY Sector
        ORDER BY Sector
    """
    return db.query_rows(sql)


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
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE {where}
        ORDER BY Symbol
        LIMIT {int(limit)}
    """
    return db.query_rows(sql, params)


def get_stock(symbol: str):
    sql = f"""
        SELECT Symbol, Sector, LTP, Open, High, Low, Close, YCP,
               ROUND(Change, 2) AS Change, ROUND(__Change, 2) AS ChangePct,
               Volume_Qty_, Value_Turnover_, EPS
        FROM {db.table_id('lankabd_datamatrix')}
        WHERE Symbol = @symbol
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper())]
    rows = db.query_rows(sql, params)
    return rows[0] if rows else None


def top_movers(limit: int = 10):
    sql = f"""
        SELECT Symbol, Sector, LTP, ROUND(__Change, 2) AS ChangePct
        FROM {db.table_id('lankabd_datamatrix')}
        ORDER BY __Change DESC
        LIMIT {int(limit)}
    """
    gainers = db.query_rows(sql)

    sql = f"""
        SELECT Symbol, Sector, LTP, ROUND(__Change, 2) AS ChangePct
        FROM {db.table_id('lankabd_datamatrix')}
        ORDER BY __Change ASC
        LIMIT {int(limit)}
    """
    losers = db.query_rows(sql)

    return {"gainers": gainers, "losers": losers}


def price_history(symbol: str, days: int = 365):
    sql = f"""
        SELECT Date, Symbol, LTP, High, Low, OPENP_ AS Open, Close, YCP,
               ROUND(Change__, 2) AS ChangePct, Volume_Qty_ AS Volume,
               SMA_20, RSI
        FROM {db.table_id('lankabd_price_archive')}
        WHERE Symbol = @symbol
        ORDER BY Date DESC
        LIMIT {int(days)}
    """
    params = [bigquery.ScalarQueryParameter("symbol", "STRING", symbol.upper())]
    return db.query_rows(sql, params)


def technical_indicators(symbol: str, days: int = 365):
    """Compute the v1 technical-indicator bundle (spec 4) from price history.

    Indicators are computed on-read in Python rather than stored in a
    precomputed BigQuery table — see ticket #31. This is the canonical indicator
    source; the raw SMA_20/RSI columns in lankabd_price_archive are left as
    scraped passthrough on price_history and are not reconciled here.
    """
    rows = price_history(symbol, days=days)
    closes, highs, lows, volumes = price_series.from_price_history(rows)
    if not closes:
        return {"symbol": symbol.upper(), "indicators": None, "points": 0}

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
        FROM {db.table_id('lankabd_announcements')}
        WHERE {where}
        ORDER BY Date DESC
        LIMIT {int(limit)}
    """
    return db.query_rows(sql, params)


def market_summary():
    sql = f"""
        SELECT COUNT(*) AS total_stocks,
               COUNT(DISTINCT Sector) AS total_sectors,
               ROUND(AVG(LTP), 2) AS avg_price,
               ROUND(SUM(Value_Turnover_), 2) AS total_turnover,
               MAX(updated_at) AS last_updated
        FROM {db.table_id('lankabd_datamatrix')}
    """
    rows = db.query_rows(sql)
    return rows[0] if rows else {}
