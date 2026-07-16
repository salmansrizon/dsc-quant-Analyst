"""Read-only market-data queries (split from the bq_service god module, #43)."""
from google.cloud import bigquery

from . import indicators
from . import db

bq = db.client()
_full_id = db.table_id


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
    precomputed BigQuery table — see ticket #31. This is the canonical indicator
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
